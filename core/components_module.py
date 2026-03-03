from abc import ABC, abstractmethod
from abc import ABC, abstractmethod

from core.results.execution_result import ExecutionResult

class Component(ABC):

    @abstractmethod
    def execute(self) -> ExecutionResult:
        """
        Contract:
        - Must return ExecutionResult
        - Must not terminate system
        """
        pass