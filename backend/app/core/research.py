import json
import logging
import time
from datetime import UTC, datetime

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, HttpUrl

from app.core.config import Settings
from app.core.errors import ProviderUnavailable

logger = logging.getLogger(__name__)


class ResearchEvidence(BaseModel):
    id: str
    source: str
    observed_at: datetime
    url: HttpUrl | None = None
    content: str


class EvidenceResearchResult(BaseModel):
    direction: str
    summary: str
    uncertainty: str
    evidence: list[ResearchEvidence]
    generated_at: datetime
    source: str


class ResearchExecution(BaseModel):
    result: EvidenceResearchResult
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    api_cost: float | None = None
    retries: int = 0


class OpenAIResearchProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key or not settings.openai_model:
            raise ProviderUnavailable(
                "OpenAI",
                "OPENAI_API_KEY and OPENAI_MODEL must be configured for research.",
            )
        self._client = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0)
        self._model = settings.openai_model

    async def analyze(
        self,
        question: str,
        evidence: list[ResearchEvidence],
    ) -> EvidenceResearchResult:
        execution = await self.analyze_with_telemetry(question, evidence)
        return execution.result

    async def analyze_with_telemetry(
        self,
        question: str,
        evidence: list[ResearchEvidence],
    ) -> ResearchExecution:
        started = time.perf_counter()
        if not evidence:
            return ResearchExecution(
                result=EvidenceResearchResult(
                    direction="abstain",
                    summary="Insufficient verified source data; analysis abstained.",
                    uncertainty="High: no current evidence is available.",
                    evidence=[],
                    generated_at=datetime.now(UTC),
                    source="NEXTRADE evidence-gated research",
                ),
                model=self._model,
                latency_ms=0,
                input_tokens=None,
                output_tokens=None,
            )
        allowed_ids = {item.id for item in evidence}
        prompt = {
            "question": question,
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Analyze only the evidence provided. Do not add outside facts or "
                            "causal claims. If evidence is insufficient or conflicting, use "
                            "direction=abstain and state uncertainty. Return JSON with keys "
                            "direction (bullish, bearish, neutral, abstain), summary, "
                            "uncertainty, evidence_ids (IDs from the provided evidence only)."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, default=str)},
                ],
            )
        except OpenAIError as error:
            logger.warning("openai_research_failed error=%s", type(error).__name__)
            raise ProviderUnavailable(
                "OpenAI", "Research provider could not complete the request."
            ) from error
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ProviderUnavailable("OpenAI", "Research provider returned an empty analysis.")
        try:
            result = json.loads(content)
            direction = result["direction"]
            if direction not in {"bullish", "bearish", "neutral", "abstain"}:
                raise ValueError("invalid direction")
            referenced_ids = result["evidence_ids"]
            if not isinstance(referenced_ids, list) or not set(referenced_ids).issubset(
                allowed_ids
            ):
                raise ValueError("research referenced unknown evidence")
            selected = [item for item in evidence if item.id in referenced_ids]
            if direction != "abstain" and not selected:
                direction = "abstain"
            return ResearchExecution(
                result=EvidenceResearchResult(
                    direction=direction,
                    summary=str(result["summary"]),
                    uncertainty=str(result["uncertainty"]),
                    evidence=selected,
                    generated_at=datetime.now(UTC),
                    source=f"OpenAI ({self._model})",
                ),
                model=self._model,
                latency_ms=int((time.perf_counter() - started) * 1000),
                input_tokens=response.usage.prompt_tokens if response.usage else None,
                output_tokens=response.usage.completion_tokens if response.usage else None,
            )
        except (ValueError, KeyError, TypeError) as error:
            raise ProviderUnavailable(
                "OpenAI", "Research provider returned an invalid evidence response."
            ) from error
