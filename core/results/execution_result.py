# core/execution_result.py
from dataclasses import dataclass
from typing import Optional
from core.results import ComponentResult

@dataclass
class ExecutionResult:
    success: bool
    short_circuit: bool = False
    message: str = ""
    data: Optional[ComponentResult] = None