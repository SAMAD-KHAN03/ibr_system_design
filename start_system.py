from BRA_analysis_module import BRAAnalysisEngine
from domain.services.approval_status_service import ApprovalStatus
from contraindication import Contraindication
from pubmed import Pubmed
from scoring.approval_status_scoring import ApprovalStatusRule
from scoring.engine import ScoringEngine
scoringengine=ScoringEngine(override_rules=[],rules=[ApprovalStatusRule()])
engine = BRAAnalysisEngine(scoring_engine=scoringengine)
engine.add_sequential(ApprovalStatus())
engine.execute(drug_data={},patient_data={})