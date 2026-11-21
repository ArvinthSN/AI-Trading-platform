from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.database import get_database_session
from app.domains.agents.approval import contains_risk_parameter, is_approvable_validation
from app.domains.agents.models import AgentStrategyVersion
from app.domains.agents.repositories import AgentRepository
from app.domains.agents.schemas import (
    AgentCommunicationResponse,
    AgentDashboardResponse,
    AgentEventResponse,
    AgentObservabilityResponse,
    AgentRosterEntry,
    AgentRunCreate,
    AgentRunResponse,
    AgentSimulationResponse,
    AgentTelemetryResponse,
    AgentTuningProposalCreate,
    AgentTuningProposalResponse,
    DebateDecision,
    Evidence,
    ExecutionAgentOutput,
    PerformanceMetrics,
    ScenarioSimulationRequest,
    StrategyVersionCreate,
)
from app.domains.agents.services.orchestrator import AGENT_NAMES, AgentOrchestrator

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_database_session)]


def _orchestrator(request: Request) -> AgentOrchestrator:
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Agent workflows are unavailable until PostgreSQL and the "
                "LangGraph checkpoint store are configured."
            ),
        )
    return orchestrator


def _run_response(run) -> AgentRunResponse:
    return AgentRunResponse.model_validate(run)


@router.get("/dashboard", response_model=AgentDashboardResponse)
async def get_dashboard(
    session: DbSession,
    user: CurrentUser,
) -> AgentDashboardResponse:
    repository = AgentRepository(session)
    runs = await repository.list_runs(user.subject)
    latest = runs[0] if runs else None
    decisions = await repository.get_decisions(latest.id) if latest else []
    by_agent = {item.agent: item for item in decisions}
    events = await repository.get_events(latest.id) if latest else []
    latest_events = {
        event.node: event for event in events if event.node
    }
    agent_states: list[AgentRosterEntry] = []
    for name in AGENT_NAMES:
        decision = by_agent.get(name)
        if decision:
            status = {
                "accepted": "accepted",
            }.get(decision.status, decision.status)
            agent_states.append(
                AgentRosterEntry(
                    agent=name,
                    status=status,
                    last_run_at=decision.created_at,
                    detail=decision.rationale if status != "completed" else None,
                )
            )
        else:
            event = latest_events.get(name)
            status_by_event = {
                "node_started": "running",
                "node_completed": "completed",
                "node_failed": "failed",
            }
            agent_states.append(
                AgentRosterEntry(
                    agent=name,
                    status=status_by_event.get(event.event_type, "not_started"),
                    last_run_at=event.created_at if event else None,
                    detail="No persisted execution is available." if not event else None,
                )
            )
    run_result = latest.result_payload if latest and latest.result_payload else {}
    evaluation_data = await repository.get_latest_evaluations(user.subject)
    return AgentDashboardResponse(
        status="available",
        runs=[_run_response(run) for run in runs],
        agents=agent_states,
        latest_decision=(
            DebateDecision.model_validate(run_result["decision"])
            if run_result.get("decision")
            else None
        ),
        latest_execution=(
            ExecutionAgentOutput.model_validate(run_result["execution"])
            if run_result.get("execution")
            else None
        ),
        latest_evidence=[
            Evidence.model_validate(item) for item in run_result.get("evidence", [])
        ],
        latest_events=[
            AgentEventResponse.model_validate(event, from_attributes=True)
            for event in events
        ],
        performance={
            agent: PerformanceMetrics.model_validate(metrics)
            for agent, metrics in evaluation_data.items()
        },
    )


@router.post("/runs", response_model=AgentRunResponse, status_code=202)
async def create_run(
    request: Request,
    body: AgentRunCreate,
    session: DbSession,
    user: CurrentUser,
) -> AgentRunResponse:
    orchestrator = _orchestrator(request)
    repository = AgentRepository(session)
    run = await repository.create_run(user.subject, body.symbol, body.interval)
    await session.commit()
    await orchestrator.start(run.id)
    return _run_response(run)


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_run(
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> AgentRunResponse:
    run = await AgentRepository(session).get_run(run_id, user.subject)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return _run_response(run)


@router.get("/runs/{run_id}/events", response_model=list[AgentEventResponse])
async def get_run_events(
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> list[AgentEventResponse]:
    repository = AgentRepository(session)
    if await repository.get_run(run_id, user.subject) is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return [
        AgentEventResponse.model_validate(event, from_attributes=True)
        for event in await repository.get_events(run_id)
    ]


@router.get(
    "/runs/{run_id}/observability",
    response_model=AgentObservabilityResponse,
)
async def get_run_observability(
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> AgentObservabilityResponse:
    repository = AgentRepository(session)
    if await repository.get_run(run_id, user.subject) is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return AgentObservabilityResponse(
        run_id=run_id,
        events=[
            AgentEventResponse.model_validate(event, from_attributes=True)
            for event in await repository.get_events(run_id)
        ],
        telemetry=[
            AgentTelemetryResponse.model_validate(item, from_attributes=True)
            for item in await repository.get_telemetry(run_id)
        ],
        communications=[
            AgentCommunicationResponse.model_validate(item, from_attributes=True)
            for item in await repository.get_communications(run_id)
        ],
    )


@router.post("/runs/{run_id}/pause", response_model=AgentRunResponse)
async def pause_run(
    request: Request,
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> AgentRunResponse:
    orchestrator = _orchestrator(request)
    try:
        await orchestrator.pause(run_id, user.subject)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    run = await AgentRepository(session).get_run(run_id, user.subject)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return _run_response(run)


@router.post("/runs/{run_id}/resume", response_model=AgentRunResponse, status_code=202)
async def resume_run(
    request: Request,
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> AgentRunResponse:
    orchestrator = _orchestrator(request)
    try:
        await orchestrator.resume(run_id, user.subject)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    run = await AgentRepository(session).get_run(run_id, user.subject)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return _run_response(run)


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_run(
    request: Request,
    run_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> AgentRunResponse:
    orchestrator = _orchestrator(request)
    try:
        await orchestrator.cancel(run_id, user.subject)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    run = await AgentRepository(session).get_run(run_id, user.subject)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return _run_response(run)


@router.post("/strategy-versions/{version_id}/approve")
async def approve_strategy(
    version_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    strategy = await session.get(AgentStrategyVersion, version_id)
    if strategy is None or strategy.owner_id != user.subject:
        raise HTTPException(status_code=404, detail="Strategy version not found.")
    if strategy.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft versions can be approved.")
    if not is_approvable_validation(strategy.validation):
        raise HTTPException(
            status_code=409,
            detail=(
                "Approval requires server-verified out-of-sample evidence, "
                "no detected overfitting, and paper-only scope."
            ),
        )
    if contains_risk_parameter(strategy.parameters):
        raise HTTPException(
            status_code=422,
            detail="Strategy approval cannot modify risk limits.",
        )
    strategy.status = "approved"
    strategy.approved_by = user.subject
    strategy.approved_at = datetime.now(UTC)
    await session.commit()
    return {"status": "approved", "version_id": str(strategy.id)}


@router.post("/strategy-versions", status_code=201)
async def create_strategy_version(
    body: StrategyVersionCreate,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    if contains_risk_parameter(body.parameters):
        raise HTTPException(
            status_code=422,
            detail="Strategy parameters cannot define risk limits.",
        )
    strategy = AgentStrategyVersion(
        owner_id=user.subject,
        name=body.name,
        version=body.version,
        parameters=body.parameters,
        status="draft",
    )
    session.add(strategy)
    await session.commit()
    return {"id": str(strategy.id), "status": strategy.status}


@router.get("/simulations", response_model=list[AgentSimulationResponse])
async def list_simulations(
    session: DbSession,
    user: CurrentUser,
) -> list[AgentSimulationResponse]:
    simulations = await AgentRepository(session).get_simulations(user.subject)
    return [
        AgentSimulationResponse.model_validate(item, from_attributes=True)
        for item in simulations
    ]


@router.post("/simulations", status_code=503)
async def create_simulation(
    body: ScenarioSimulationRequest,
    request: Request,
    user: CurrentUser,
) -> None:
    del body, user
    if getattr(request.app.state, "agent_simulator", None) is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Scenario and backtest provider is not configured. "
                "No simulated result was created."
            ),
        )
    raise HTTPException(
        status_code=503,
        detail="The configured simulation provider does not expose a compatible contract.",
    )


@router.post("/tuning-proposals", response_model=AgentTuningProposalResponse, status_code=201)
async def create_tuning_proposal(
    body: AgentTuningProposalCreate,
    session: DbSession,
    user: CurrentUser,
) -> AgentTuningProposalResponse:
    if contains_risk_parameter(body.candidate_parameters):
        raise HTTPException(
            status_code=422,
            detail="Tuning proposals cannot change risk limits.",
        )
    base = await session.get(AgentStrategyVersion, body.base_strategy_version_id)
    if base is None or base.owner_id != user.subject or base.status != "approved":
        raise HTTPException(status_code=404, detail="Approved base strategy not found.")
    proposal = await AgentRepository(session).create_tuning_proposal(
        user.subject,
        base.id,
        body.candidate_parameters,
    )
    await session.commit()
    return AgentTuningProposalResponse.model_validate(proposal)


@router.post("/tuning-proposals/{proposal_id}/validate", status_code=503)
async def validate_tuning_proposal(
    proposal_id: UUID,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> None:
    proposal = await AgentRepository(session).get_tuning_proposal(proposal_id, user.subject)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Tuning proposal not found.")
    if getattr(request.app.state, "agent_tuner", None) is None:
        raise HTTPException(
            status_code=503,
            detail="Out-of-sample backtest provider is unavailable; proposal remains unvalidated.",
        )
    raise HTTPException(
        status_code=503,
        detail="The configured tuner does not expose a compatible validation contract.",
    )


@router.post("/tuning-proposals/{proposal_id}/approve")
async def approve_tuning_proposal(
    proposal_id: UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, str]:
    proposal = await AgentRepository(session).get_tuning_proposal(proposal_id, user.subject)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Tuning proposal not found.")
    if proposal.status != "draft" or not is_approvable_validation(proposal.validation):
        raise HTTPException(
            status_code=409,
            detail="Only server-validated, non-overfit, paper-only proposals can be approved.",
        )
    if contains_risk_parameter(proposal.candidate_parameters):
        raise HTTPException(status_code=422, detail="Tuning cannot change risk limits.")
    proposal.status = "approved"
    proposal.approved_by = user.subject
    proposal.approved_at = datetime.now(UTC)
    await session.commit()
    return {
        "status": "approved",
        "proposal_id": str(proposal.id),
        "applied": "false",
    }


@router.websocket("/stream")
async def stream_agent_events(websocket: WebSocket, user: CurrentUser) -> None:
    hub = getattr(websocket.app.state, "agent_event_hub", None)
    if hub is None:
        await websocket.close(code=1013, reason="Agent event service unavailable.")
        return
    await websocket.accept()
    try:
        async with hub.subscribe(user.subject) as queue:
            while True:
                await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        return
