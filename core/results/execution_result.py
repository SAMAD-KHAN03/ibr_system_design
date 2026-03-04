# core/execution_result.py
from dataclasses import dataclass
from typing import Optional
from core.component_results import ComponentResult

@dataclass
class ExecutionResult:
    success: bool
    short_circuit: bool = False