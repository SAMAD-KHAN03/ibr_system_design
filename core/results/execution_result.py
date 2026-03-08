from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExecutionResult:
    """
    Returned by every Component.execute().
    short_circuit=True tells the engine to halt the pipeline immediately.
    """
    success: bool
    short_circuit: bool = False
    message: str = ""
    data: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data: dict = None) -> "ExecutionResult":
        return cls(success=True, data=data or {})

    @classmethod
    def halt(cls, reason: str) -> "ExecutionResult":
        return cls(success=False, short_circuit=True, message=reason)

    @classmethod
    def fail(cls, reason: str) -> "ExecutionResult":
        return cls(success=False, short_circuit=False, message=reason)