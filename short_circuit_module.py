from abc import ABC, abstractmethod
import time
class ShortCircuit(ABC):

    @property
    @abstractmethod
    def is_short_circuit(self):
        """short circuit occured exiting the system freeing the resources"""
        time.sleep(2)
        exit()