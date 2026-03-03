# domain/results/regulatory_result.py
from dataclasses import dataclass
from core.results import ComponentResult
from domain.enums import ApprovalCategory

@dataclass
class RegulatoryApprovalResult(ComponentResult):
    category: ApprovalCategory