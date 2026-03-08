from abc import ABC, abstractmethod
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult


class Component(ABC):
    """
    Single-Responsibility: each subclass performs exactly one analytical task.
    Open/Closed: new components are added by subclassing, not by editing the engine.

    Contract
    --------
    * execute() MUST return an ExecutionResult — never raise or sys.exit.
    * If execution should halt the pipeline, return ExecutionResult.halt(reason).
    * Store domain findings via context.add_result(ComponentResult(...)).
    """

    @property
    @abstractmethod
    def component_name(self) -> str:
        """Stable, unique identifier used as the key in context.component_results."""

    @abstractmethod
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        pass