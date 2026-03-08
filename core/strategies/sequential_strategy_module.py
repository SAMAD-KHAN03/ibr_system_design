from typing import List
from core.components_module import Component
from execution_context import ExecutionContext
from core.strategies.execution_strategy import ExecutionStrategy


class SequentialExecutionStrategy(ExecutionStrategy):
    """
    Runs components one-by-one in insertion order.
    Stops immediately if any component signals short_circuit=True.
    """

    def execute(self, components: List[Component], context: ExecutionContext) -> bool:
        for component in components:
            print(f"  [SEQ] Running: {component.component_name}")
            result = component.execute(context)

            if not result.success or result.short_circuit:
                print(f"  ⚠  Short-circuit triggered by '{component.component_name}': {result.message}")
                context.trigger_hard_stop()
                return False

        return True