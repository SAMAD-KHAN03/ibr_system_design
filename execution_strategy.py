from abc import ABC, abstractmethod
from typing import List
from core.components_module import Component

class ExecutionStrategy(ABC):

    @abstractmethod
    def execute(self, components: List[Component]) -> bool:
        """
        Returns False if short-circuit triggered
        """
        pass