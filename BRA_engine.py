from typing import List, Optional
from core.components_module import Component
from execution_context import ExecutionContext
from core.strategies.sequential_strategy_module import SequentialExecutionStrategy
from core.strategies.parallel_strategy_module import ParallelExecutionStrategy
from scoring.scoring_engine import ScoringEngine


class BRAAnalysisEngine:
    """
    Orchestrates the full Benefit-Risk Assessment pipeline:
      1. Sequential components  (order-sensitive, e.g. hard stops first)
      2. Parallel components    (independent, e.g. literature lookups)
      3. Scoring

    Adding a new component = one call to add_sequential() or add_parallel().
    No other class changes.
    """

    def __init__(
        self,
        scoring_engine: ScoringEngine,
        sequential_strategy: SequentialExecutionStrategy = None,
        parallel_strategy: ParallelExecutionStrategy = None,
    ):
        self._sequential_components: List[Component] = []
        self._parallel_components: List[Component] = []
        self._sequential_strategy = sequential_strategy or SequentialExecutionStrategy()
        self._parallel_strategy = parallel_strategy or ParallelExecutionStrategy()
        self._scoring_engine = scoring_engine

    # ── Component registration ───────────────────────────────────────────

    def add_sequential(self, component: Component) -> "BRAAnalysisEngine":
        """Fluent builder — supports method chaining."""
        self._sequential_components.append(component)
        return self

    def add_parallel(self, component: Component) -> "BRAAnalysisEngine":
        self._parallel_components.append(component)
        return self

    # ── Execution ────────────────────────────────────────────────────────

    def execute(self, patient_data: dict, drug_data: dict) -> Optional[ExecutionContext]:
        context = ExecutionContext(patient_data=patient_data, drug_data=drug_data)

        print("\n══════════════════════════════════════")
        print("  BRA Analysis Pipeline Starting")
        print("══════════════════════════════════════")

        # 1️⃣  Sequential phase
        print("\n[Phase 1] Sequential Components")
        if not self._sequential_strategy.execute(self._sequential_components, context):
            print("  Pipeline halted during sequential phase.")
            return context   # return partial context so caller can inspect warnings

        # 2️⃣  Parallel phase
        print("\n[Phase 2] Parallel Components")
        if not self._parallel_strategy.execute(self._parallel_components, context):
            print("  Pipeline halted during parallel phase.")
            return context

        # 3️⃣  Scoring
        print("\n[Phase 3] Scoring")
        context.final_score = self._scoring_engine.evaluate(context)
        print(f"  Score: {context.final_score}")

        print("\n══════════════════════════════════════\n")
        return context