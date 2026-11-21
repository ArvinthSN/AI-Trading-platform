from datetime import datetime
from uuid import uuid4

from app.core.research import ResearchEvidence


def metric_evidence(metrics: dict[str, object]) -> list[ResearchEvidence]:
    evidence: list[ResearchEvidence] = []
    for metric_name, raw in metrics.items():
        if not isinstance(raw, dict):
            continue
        value = raw.get("value")
        observed_at = raw.get("updated_at")
        source = raw.get("source")
        if value is None or observed_at is None or not source:
            continue
        try:
            timestamp = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                continue
        except ValueError:
            continue
        evidence.append(
            ResearchEvidence(
                id=f"metric-{metric_name}-{uuid4().hex[:8]}",
                source=str(source),
                observed_at=timestamp,
                content=f"{metric_name}: {value} {raw.get('unit') or ''}".strip(),
            )
        )
    return evidence
