from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentResult:
    """
    Stores the outcome of a single component's analysis.
    Every component must produce one of these and register it on the context.
    """
    name: str
    metadata: dict = field(default_factory=dict)
    category: Any = None          # domain enum value used by scoring rules