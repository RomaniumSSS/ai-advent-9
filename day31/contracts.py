"""Общие контракты: модель не создаёт источники и Git-контекст."""
from dataclasses import asdict, dataclass, field
from typing import Literal


@dataclass(frozen=True)
class SourceChunk:
    id: str
    path: str
    start_line: int
    end_line: int
    section: str
    text: str
    sha256: str
    score: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class Answer:
    status: Literal['ok', 'unknown', 'error']
    text: str
    source_ids: list[str]
    git_context: dict | None
    trace_id: str
    sources: list[dict] = field(default_factory=list)
    stages: list[dict] = field(default_factory=list)
    usage: dict | None = None
    elapsed_seconds: float = 0.0
    model: str | None = None
    provider: str | None = None

    def to_dict(self):
        return asdict(self)
