from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from core.components_module import Component
from execution_context import ExecutionContext
from core.strategies.execution_strategy import ExecutionStrategy


class ParallelExecutionStrategy(ExecutionStrategy):
    """
    Runs all components concurrently using a thread pool.
    If any component signals short_circuit, the whole batch is considered failed.

    Note: context.add_result() is safe here only if components write to
    different keys. If two components write the same key, last-write-wins —
    callers must ensure uniqueness of component_name.
    """

    def __init__(self, max_workers: int = None):
        self._max_workers = max_workers  # None → ThreadPoolExecutor default

    def execute(self, components: List[Component], context: ExecutionContext) -> bool:
        if not components:
            return True

        short_circuited = False

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_name = {
                executor.submit(c.execute, context): c.component_name
                for c in components
            }

            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    result = future.result()
                    print(f"  [PAR] Finished: {name}")
                    if result.short_circuit:
                        print(f"  ⚠  Short-circuit triggered by '{name}': {result.message}")
                        short_circuited = True
                except Exception as exc:
                    print(f"  ✗  Exception in '{name}': {exc}")
                    short_circuited = True

        if short_circuited:
            context.trigger_hard_stop()
            return False
        return True