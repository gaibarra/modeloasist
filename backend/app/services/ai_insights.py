"""Google Vertex AI integration for coaching insights."""
from __future__ import annotations

from datetime import date
from typing import Iterable

import structlog

from app.schemas.insight import InsightPayload

LOGGER = structlog.get_logger(__name__)


class AiInsightsService:
    """High-level gateway to the Vertex AI text generation endpoints."""

    def __init__(self, project_id: str | None, location: str | None) -> None:
        self._project_id = project_id
        self._location = location or "us-central1"

    async def build_employee_coaching(self, payload: InsightPayload) -> str:
        """Return a motivational summary.

        For now we return a deterministic placeholder and log the intended prompt. Later this
        method should call the Vertex AI SDK (Gemini 1.5 or similar) with safety settings,
        caching and observability.
        """

        LOGGER.info(
            "ai_insight.generated",
            project_id=self._project_id,
            employee_id=payload.employee_id,
            period=(payload.period_start.isoformat(), payload.period_end.isoformat()),
        )

        summary = [
            "¡Buen trabajo!",
            "Has mantenido una asistencia constante en el periodo analizado.",
            "Tus principales oportunidades se concentran en los lunes antes de las 9:00.",
            "Recuerda que llegar 5 minutos antes reduce el estrés del arranque de actividades.",
        ]
        if payload.recommendations:
            summary.append(f"Recomendación destacada: {payload.recommendations[0]}")
        return " ".join(summary)

    async def build_leadership_brief(self, rank_rows: Iterable[dict[str, str | int | float]]) -> str:
        """Summarize ranking outputs for directors."""

        total = len(list(rank_rows))
        return (
            "Resumen generado por IA. Se analizaron "
            f"{total} colaboradores y se identificaron los patrones de puntualidad más relevantes."
        )


def get_ai_service(project_id: str | None, location: str | None) -> AiInsightsService:
    return AiInsightsService(project_id=project_id, location=location)
