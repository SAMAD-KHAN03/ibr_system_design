from abc import ABC, abstractmethod
from abc import ABC, abstractmethod

from core.results.execution_result import ExecutionResult
from execution_context import ExecutionContext
class Component(ABC):

    @abstractmethod
    def execute(self,context: ExecutionContext) -> ExecutionResult:
        """
        Contract:
        - Must return ExecutionResult
        - Must not terminate system
        """
        pass