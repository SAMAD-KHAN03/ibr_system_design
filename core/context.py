# core/context.py

class ExecutionContext:

    def __init__(self, patient=None, medical=None):
        self.patient = patient
        self.medical = medical
        self.results = {}         # component_name → ComponentResult
        self.final_score = None   # populated after scoring