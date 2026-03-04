from core.components_module import Component

from core.components_module import Component
from sequential_strategy_module import SequentialExecutionStrategy
from parallel_strategy_module import ParallelExecutionStrategy
from scoring.engine import ScoringEngine
from execution_context import ExecutionContext
class BRAAnalysisEngine:

    def __init__(self, scoring_engine: ScoringEngine):
        self._sequential_components = []
        self._parallel_components = []
        self._sequential_strategy = SequentialExecutionStrategy()
        self._parallel_strategy = ParallelExecutionStrategy()
        self._scoring_engine = scoring_engine

    def add_sequential(self, component: Component):
        self._sequential_components.append(component)

    def add_parallel(self, component: Component):
        self._parallel_components.append(component)

    def execute(self, patient_data: dict, drug_data: dict):

        context = ExecutionContext(patient_data, drug_data)

        # 1️⃣ Sequential
        if not self._sequential_strategy.execute(self._sequential_components, context):
            return None

        # 2️⃣ Parallel
        if not self._parallel_strategy.execute(self._parallel_components, context):
            return None

        # 3️⃣ Scoring
        score_result = self._scoring_engine.evaluate(context)
        context.final_score = score_result

        return context