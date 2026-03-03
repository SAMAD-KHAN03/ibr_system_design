from concurrent.futures import ThreadPoolExecutor
from execution_strategy import ExecutionStrategy
class SequentialExecutionStrategy(ExecutionStrategy):

    def execute(self, components):
        print("\n--- Sequential Strategy ---")

        def worker():
            for component in components:
                result = component.execute()
                if result.short_circuit:
                    print(f"⚠ Short Circuit: {result.message}")
                    return False
            return True

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(worker)
            return future.result()