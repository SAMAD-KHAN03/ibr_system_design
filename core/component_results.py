# core/results.py
from abc import ABC
class ComponentResult:

    def __init__(self, name: str, metadata=None):
        self.name = name
        self.metadata = metadata or {}