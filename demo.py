from BRA_analysis_module import BRAAnalysisEngine
from approvalstatus import ApprovalStatus
from contraindication import Contraindication
from pubmed import Pubmed
engine = BRAAnalysisEngine()

engine.add_sequential(ApprovalStatus())
engine.add_sequential(Contraindication())
engine.add_sequential(Pubmed())
engine.execute()