# scoring/base_rule.py
from abc import ABC, abstractmethod

class ScoreRule(ABC):

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, context) -> float:
        pass

    @abstractmethod
    def max_score(self) -> float:
        pass