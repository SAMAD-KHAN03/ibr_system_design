from dataclasses import dataclass, field
from typing import Any, Dict, List
from core.results.component_results import ComponentResult

COMPONENT_NAME = "RMM"


@dataclass
class RMMResult(ComponentResult):
    """
    Stores the Risk Minimization Measures table (Step 4).
    category is None — RMM is informational, not scored directly.
    rmm_table is the list of entries for use in reports.
    """
    rmm_table: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def build(cls, rmm_table: List[Dict[str, Any]]) -> "RMMResult":
        total    = len(rmm_table)
        
        lt_count = sum(1 for e in rmm_table if "LT" in e.get("risk_type", ""))
        output   = (
            f"RMM table generated: {total} entries "
            f"({lt_count} life-threatening, {total - lt_count} serious/interaction)"
        )
        # print(f'{rmm_table}')
        return cls(
            name=COMPONENT_NAME,
            category=None,
            rmm_table=rmm_table,
            metadata={
                "total_entries": total,
                "lt_entries":    lt_count,
                "output":        output,
                "rmm_table":     rmm_table,
            },
        )
