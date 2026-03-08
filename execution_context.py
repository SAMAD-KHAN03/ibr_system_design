from __future__ import annotations
from typing import Optional
from core.results.component_results import ComponentResult


class ExecutionContext:
    """
    Immutable-ish pipeline state passed through every component.

    Design decisions
    ----------------
    * patient_data / drug_data stay as plain dicts so callers are not
      forced to construct domain objects before running the engine.
    * component_results is keyed by component name; scoring rules read from here.
    * hard_stop signals that the pipeline should abort immediately.
    """

    def __init__(self, patient_data: dict, drug_data: dict):
        self.patient_data: dict = patient_data
        self.drug_data: dict = drug_data
        self.component_results: dict[str, ComponentResult] = {}
        self.warnings: list[str] = []
        self.hard_stop: bool = False
        self.final_score: Optional[dict] = None

    # ── Mutation helpers ────────────────────────────────────────────────────

    def add_result(self, result: ComponentResult) -> None:
        self.component_results[result.name] = result

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def trigger_hard_stop(self) -> None:
        self.hard_stop = True

    # ── Convenience accessors ───────────────────────────────────────────────

    def get_result(self, name: str) -> Optional[ComponentResult]:
        return self.component_results.get(name)

    @property
    def drug_name(self) -> str:
        return self.drug_data.get("name", "")

    @property
    def condition(self) -> str:
        return self.drug_data.get("condition", "")