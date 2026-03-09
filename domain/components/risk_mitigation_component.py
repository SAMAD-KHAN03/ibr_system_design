from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.adr_result import COMPONENT_NAME as ADR_COMPONENT_NAME
from domain.results.risk_mitigation_result import RiskMitigationResult, COMPONENT_NAME
from infrastructure.risk_mitigation_feasability.risk_mitigation_analyzer import RiskMitigationAnalyzer


class RiskMitigationComponent(Component):
    """
    Factor 3.4: Risk Mitigation Feasibility (R4 Preventability + R5 Reversibility).

    Can run in parallel after RMMComponent — both RMM and RiskMitigation only
    require ADRResult to be present on context, which ADRComponent guarantees.

    Stores: RiskMitigationResult on context under key "RiskMitigation"
    """

    def __init__(self):
        self._analyzer = RiskMitigationAnalyzer()

    @property
    def component_name(self) -> str:
        return COMPONENT_NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        adr_result = context.get_result(ADR_COMPONENT_NAME)
        if adr_result is None:
            return ExecutionResult.fail(
                reason="RiskMitigationComponent requires ADRComponent to run first"
            )

        try:
            mitigation_analysis = self._analyzer.analyze(
                adr_analysis=adr_result.raw,
                patient_data=context.patient_data,
                drug_data=context.drug_data,
            )
            result = RiskMitigationResult.build(mitigation_analysis)
            context.add_result(result)

            print(f"  [RiskMitigationComponent] "
                  f"R4={result.category.value}, R5={result.reversibility_category.value}")
            return ExecutionResult.ok(data={
                "preventability": result.category.value,
                "reversibility":  result.reversibility_category.value,
            })

        except Exception as exc:
            print(f"  [RiskMitigationComponent] Error: {exc}")
            return ExecutionResult.fail(reason=str(exc))
