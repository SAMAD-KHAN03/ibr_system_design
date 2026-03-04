from concurrent.futures import ThreadPoolExecutor
from execution_strategy import ExecutionStrategy
from execution_context import ExecutionContext

class SequentialExecutionStrategy(ExecutionStrategy):

    def execute(self, components, context: ExecutionContext):
        print("\n--- Sequential Strategy ---")

        def worker():
            for component in components:
                result = component.execute(context)
                if result.short_circuit:
                    print(f"⚠ Short Circuit: {result.message}")
                    return False
            return True

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(worker)
            return future.result()