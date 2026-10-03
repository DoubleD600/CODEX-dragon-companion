from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    state: str = "idle"
    context_used: int | None = None
    context_window: int | None = None
    updated_at: float = 0

    @property
    def context_percent(self):
        if self.context_used is None or not self.context_window:
            return None
        return round(max(0, min(100, 100 * self.context_used / self.context_window)))


@dataclass(frozen=True)
class Snapshot:
    tasks: list[Task] = field(default_factory=list)
    rate_limits: dict | None = None
    error: str | None = None


class TaskProvider(Protocol):
    """Adapters return normalized metadata; UI never accesses logs directly."""
    def snapshot(self) -> Snapshot: ...
