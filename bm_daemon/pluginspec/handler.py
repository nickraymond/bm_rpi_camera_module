from typing import Protocol, Iterable, Dict, Any

class Handler(Protocol):
    topics: Iterable[str]
    def handle(self, msg: Dict[str, Any], *, ctx: dict) -> None: ...
