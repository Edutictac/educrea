from dataclasses import dataclass, field


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ProviderResult:
    text: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class ProviderChunk:
    text: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    finished: bool = False

