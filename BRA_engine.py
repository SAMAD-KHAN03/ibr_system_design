from typing import List, Optional
from core.components_module import Component
from execution_context import ExecutionContext
from core.strategies.sequential_strategy_module import SequentialExecutionStrategy
from core.strategies.parallel_strategy_module import ParallelExecutionStrategy
from scoring.scoring_engine import ScoringEngine
from concurrent.futures import ThreadPoolExecutor


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

        def run_sequential():
            print("\n[Phase 1] Sequential Components")
            return self._sequential_strategy.execute(self._sequential_components, context)

        def run_parallel():
            print("\n[Phase 2] Parallel Components")
            return self._parallel_strategy.execute(self._parallel_components, context)

        # Run both phases in parallel using 2 threads
        with ThreadPoolExecutor(max_workers=2) as executor:
            sequential_future = executor.submit(run_sequential)
            parallel_future = executor.submit(run_parallel)

            sequential_success = sequential_future.result()
            parallel_success = parallel_future.result()

        # Check results
        if not sequential_success:
            print("  Pipeline halted during sequential phase.")
            return context

        if not parallel_success:
            print("  Pipeline halted during parallel phase.")
            return context

        # Scoring only after both are done
        print("\n[Phase 3] Scoring")
        context.final_score = self._scoring_engine.evaluate(context)
        print(f"  Score: {context.final_score}")

        print("\n══════════════════════════════════════\n")
        return context