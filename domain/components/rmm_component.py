from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.adr_result import COMPONENT_NAME as ADR_COMPONENT_NAME
from domain.results.rmm_result import RMMResult, COMPONENT_NAME
from infrastructure.rmm_infrastructure.rmm_generator import RMMGenerator


class RMMComponent(Component):
    """
    Step 4: Risk Minimization Measures generation.

    Sequential phase — MUST run after ADRComponent (depends on ADRResult on context).
    Reads the raw ADR analysis dict from ADRResult.raw, generates the RMM table,
    and stores RMMResult on context under key "RMM".

    No file I/O — all data flows through ExecutionContext.
    """

    def __init__(self):
        self._generator = RMMGenerator()

    @property
    def component_name(self) -> str:
        return COMPONENT_NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        # Depend on ADRComponent having run first
        adr_result = context.get_result(ADR_COMPONENT_NAME)
        if adr_result is None:
            return ExecutionResult.fail(
                reason="RMMComponent requires ADRComponent to run first (ADRResult not found on context)"
            )

        try:
            rmm_table = self._generator.generate(
                adr_analysis=adr_result.raw,
                patient_data=context.patient_data,
                drug_data=context.drug_data,
            )
            result = RMMResult.build(rmm_table)
            context.add_result(result)

            print(f"  [RMMComponent] RMM table generated: {len(rmm_table)} entries")
            return ExecutionResult.ok(data={"rmm_entries": len(rmm_table)})

        except Exception as exc:
            print(f"  [RMMComponent] Error: {exc}")
            return ExecutionResult.fail(reason=str(exc))
