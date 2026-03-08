from enum import Enum


class ApprovalCategory(Enum):
    APPROVED = "approved"
    OFF_LABEL = "off_label"
    NOT_FOUND = "not_found"


class ContraindicationCategory(Enum):
    SAFE          = "safe"          # no contraindications found
    ABSOLUTE      = "absolute"      # hard FDA contraindication
    BOXED_WARNING = "boxed_warning" # black-box warning triggered
    PREGNANCY     = "pregnancy"     # pregnancy / lactation risk


class PubMedEvidenceCategory(Enum):
    HIGH    = "high"    # rct_count >= 10
    MEDIUM  = "medium"  # rct_count 1-9
    LOW     = "low"     # rct_count == 0


class AlternativeScoreCategory(Enum):
    SCORED    = "scored"     # alternative ran through full pipeline
    FAILED    = "failed"     # pipeline error for this alternative
    NOT_FOUND = "not_found"  # no alternatives found at all
