# this class would be the template for every component will extend

from abc import ABC, abstractmethod
from typing import Dict, Any


class ScoringTemplate(ABC):
    """
    Base abstract class for all scoring systems.
    """

    def __init__(self, description: str, score_map: Dict[str, float]):
        """
        Args:
            description: Explanation of what this scoring system represents
            score_map: Mapping of condition → score value
        """
        self._description = description
        self._score_map = score_map

    # --------------------------
    # Properties (read-only)
    # --------------------------

    @property
    def description(self) -> str:
        return self._description

    @property
    def score_map(self) -> Dict[str, float]:
        return self._score_map

    # --------------------------
    # Abstract Behavior
    # --------------------------

    @abstractmethod
    def calculate(self, **kwargs) -> float:
        """
        Child classes must implement scoring logic.
        Returns:
            Final numeric score
        """
        pass
    
