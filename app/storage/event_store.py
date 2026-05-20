from __future__ import annotations

from app.config import Settings
from app.core.state import FusedState, InsideState, OutsideState


class EventStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def maybe_log_event(
        self,
        fused: FusedState,
        inside_state: InsideState,
        outside_state: OutsideState,
        inside_frame,
        outside_frame,
    ) -> None:
        # Incident history is intentionally disabled for the current build.
        return None

    def fetch_recent(self, limit: int = 10) -> list[dict]:
        return []

    def fetch_events(
        self,
        limit: int = 24,
        risk_level: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        return []
