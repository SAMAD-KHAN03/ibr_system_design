from core.components_module import Component
from execution_context import ExecutionContext
from core.results.execution_result import ExecutionResult
from domain.results.severity_result import SeverityResult, COMPONENT_NAME
from infrastructure.disease_severity_infrastructure.disease_severity_analyzer import DiseaseSeverityAnalyzer


class DiseaseSeverityComponent(Component):
    """
    Factor 2.6: Consequences of Non-Treatment (B6 Disease Severity).

    Parallel phase — independent of ADR pipeline.
    Calls Gemini to classify each patient diagnosis by severity category,
    then maps the worst-case to SeverityCategory for SeverityRule (B6).

    Stores: SeverityResult on context under key "DiseaseSeverity"
    """

    def __init__(self):
        self._analyzer = DiseaseSeverityAnalyzer()

    @property
    def component_name(self) -> str:
        return COMPONENT_NAME

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        try:
            severity_analysis = self._analyzer.analyze(
                patient_data=context.patient_data,
                drug_data=context.drug_data,
            )
            result = SeverityResult.build(severity_analysis)
            context.add_result(result)

            print(f"  [DiseaseSeverityComponent] severity={result.category.value}")
            return ExecutionResult.ok(data={"severity_category": result.category.value})

        except Exception as exc:
            print(f"  [DiseaseSeverityComponent] Error: {exc}")
            return ExecutionResult.fail(reason=str(exc))
