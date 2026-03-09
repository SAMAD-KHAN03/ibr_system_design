from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.adr_result import ADRResult, COMPONENT_NAME
from infrastructure.adr_infrastructure.adr_analyzer import ADRAnalyzer
from infrastructure.adr_infrastructure.patient_adapter import to_adr_patient_data


class ADRComponent(Component):
    """
    Factor 3.2 (LT + Serious ADRs) and Factor 3.3 (Drug Interactions).

    Sequential phase — runs before RMMComponent and RiskMitigationComponent
    because both of those depend on the ADR analysis output stored on context.

    Stores: ADRResult on context under key "ADRAnalysis"
    """

    def __init__(self):
        self._analyzer = ADRAnalyzer()

    @property
    def component_name(self) -> str:
        return COMPONENT_NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        try:
            # Adapt our system's patient_data schema to the ADR analyzer's expected schema
            patient_data_adapted = to_adr_patient_data(
                context.patient_data,
                context.drug_data,
            )

            analysis = self._analyzer.analyze(patient_data_adapted)
            result   = ADRResult.build(analysis)
            context.add_result(result)

            print(f"  [ADRComponent] ADR category={result.category.value}, "
                  f"interaction={result.interaction_category.value}")
            return ExecutionResult.ok(data={"adr_category": result.category.value})

        except Exception as exc:
            print(f"  [ADRComponent] Error: {exc}")
            return ExecutionResult.fail(reason=str(exc))
