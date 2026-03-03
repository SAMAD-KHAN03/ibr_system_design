from concurrent.futures import ThreadPoolExecutor, as_completed
from execution_strategy import ExecutionStrategy
class ParallelExecutionStrategy(ExecutionStrategy):

    def execute(self, components):
        print("\n--- Parallel Strategy ---")

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(c.execute) for c in components]

            for future in as_completed(futures):
                result = future.result()
                if result.short_circuit:
                    print(f"⚠ Short Circuit (Parallel): {result.message}")
                    return False

        return True