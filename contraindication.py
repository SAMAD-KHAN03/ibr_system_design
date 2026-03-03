from core.components_module import Component
from short_circuit_module import ShortCircuit
import time
from core.results.execution_result import ExecutionResult
import time

class Contraindication(Component):

    def execute(self) -> ExecutionResult:
        print("Executing Contraindication...")
        time.sleep(2)

        print("❌ Medicine contraindicated")
        return ExecutionResult(
            success=False,
            short_circuit=True,
            message="Contraindication found"
        )