from core.components_module import Component
from typing import List
from typing import List
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.components_module import Component
from sequential_strategy_module import SequentialExecutionStrategy
from parallel_strategy_module import ParallelExecutionStrategy
class BRAAnalysisEngine:

    def __init__(self):
        self._sequential_components = []
        self._parallel_components = []

        self._sequential_strategy = SequentialExecutionStrategy()
        self._parallel_strategy = ParallelExecutionStrategy()

    def add_sequential(self, component):
        self._sequential_components.append(component)

    def add_parallel(self, component):
        self._parallel_components.append(component)

    def execute(self):

        if not self._sequential_strategy.execute(self._sequential_components):
            return

        if not self._parallel_strategy.execute(self._parallel_components):
            return

        print("\n✔ Execution Completed")