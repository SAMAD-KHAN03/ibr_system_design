from core.component_results import ComponentResult
class ExecutionContext:

    def __init__(self, patient_data: dict, drug_data: dict):
        self.patient_data = patient_data
        self.drug_data = drug_data

        # Stores each component result
        self.component_results = {}

        # Final score
        self.final_score = None

        # Optional: warnings / hard stops
        self.warnings = []
        self.hard_stop = False

    def add_result(self, result:ComponentResult):
        self.component_results[result.name] = result.metadata

    def add_warning(self, message: str):
        self.warnings.append(message)

    def stop_execution(self):
        self.hard_stop = True