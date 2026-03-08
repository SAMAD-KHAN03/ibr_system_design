from enum import Enum


# ── B1: Approval Status ──────────────────────────────────────────────────────
class ApprovalCategory(Enum):
    APPROVED  = "approved"   # score=2, weight=70  → 140
    OFF_LABEL = "off_label"  # score=1, weight=50  → 50
    NOT_FOUND = "not_found"  # score=0, weight=0   → 0


# ── B2: Molecule Market Experience (MME) ─────────────────────────────────────
class MMECategory(Enum):
    ESTABLISHED = "established"  # >5Y, approved widely  → score=2, weight=60 → 120
    NEW         = "new"          # <5Y, limited approval → score=1, weight=40 → 40


# ── B3: Strength of Evidence (PubMed RCTs) ───────────────────────────────────
class PubMedEvidenceCategory(Enum):
    HIGH   = "high"    # >3 RCTs  → score=3, weight=90 → 270
    LOW    = "low"     # <=2 RCTs → score=0, weight=20 → 0


# ── B4: Therapeutic Duplication ──────────────────────────────────────────────
class DuplicationCategory(Enum):
    UNIQUE     = "unique"      # score=3, weight=80 → 240
    OVERLAP    = "overlap"     # score=2, weight=60 → 120
    REDUNDANT  = "redundant"   # score=0, weight=20 → 0


# ── B5: Alternatives ─────────────────────────────────────────────────────────
class AlternativeScoreCategory(Enum):
    NONE_EXISTS  = "none_exists"   # score=2, weight=70 → 140
    SAME_SAFETY  = "same_safety"   # score=1, weight=50 → 50
    SAFER_EXISTS = "safer_exists"  # score=0, weight=20 → 0
    NOT_FOUND    = "not_found"     # fallback


# ── B6: Severity of Disease ──────────────────────────────────────────────────
class SeverityCategory(Enum):
    ACUTE_LIFE_THREATENING     = "acute_life_threatening"     # score=3, weight=100 → 300
    ACUTE_NON_LIFE_THREATENING = "acute_non_life_threatening" # score=3, weight=90  → 270
    CHRONIC_LIFE_THREATENING   = "chronic_life_threatening"   # score=3, weight=80  → 240
    CHRONIC_NON_LIFE_THREATENING = "chronic_non_life_threatening" # score=2, weight=60 → 120
    QUALITY_OF_LIFE            = "quality_of_life"            # score=1, weight=40  → 40
    SIGNS_SYMPTOMS             = "signs_symptoms"             # score=1, weight=20  → 20


# ── R1: Contraindication ─────────────────────────────────────────────────────
class ContraindicationCategory(Enum):
    ABSOLUTE      = "absolute"      # score=3, weight=100 → 300 (OVERRIDE)
    BOXED_WARNING = "boxed_warning" # mapped to absolute override
    PREGNANCY     = "pregnancy"     # mapped to absolute override
    SAFE          = "safe"          # score=0, weight=10  → 0


# ── R2: Interactions ─────────────────────────────────────────────────────────
class InteractionCategory(Enum):
    CONTRAINDICATED  = "contraindicated"   # score=3, weight=100 → 300
    LIFE_THREATENING = "life_threatening"  # score=3, weight=90  → 270
    SERIOUS          = "serious"           # score=2, weight=70  → 140
    NON_SERIOUS      = "non_serious"       # score=1, weight=30  → 30
    NONE             = "none"              # score=0, weight=10  → 0


# ── R3: Risk Severity (ADRs) ─────────────────────────────────────────────────
class ADRSeverityCategory(Enum):
    LT_WITH_RISK_FACTORS    = "lt_with_risk_factors"     # score=3, weight=100 → 300
    LT_NO_RISK_FACTORS      = "lt_no_risk_factors"       # score=3, weight=90  → 270
    SERIOUS_WITH_RISK       = "serious_with_risk"        # score=2, weight=80  → 160
    SERIOUS_NO_RISK         = "serious_no_risk"          # score=2, weight=60  → 120
    NO_LT_SERIOUS_ADRS      = "no_lt_serious_adrs"       # score=1, weight=30  → 30
    NO_SERIOUS_ADRS         = "no_serious_adrs"          # score=0, weight=10  → 0


# ── R4: Risk Preventability ──────────────────────────────────────────────────
class PreventabilityCategory(Enum):
    NON_PREVENTABLE = "non_preventable"  # score=3, weight=80 → 240
    PREVENTABLE     = "preventable"      # score=2, weight=50 → 100


# ── R5: Risk Reversibility ───────────────────────────────────────────────────
class ReversibilityCategory(Enum):
    IRREVERSIBLE = "irreversible"  # score=3, weight=95 → 285
    REVERSIBLE   = "reversible"   # score=1, weight=40 → 40


# ── iBR Outcome thresholds (from BR analysis sheet) ─────────────────────────
# iBR score = sum(benefit weighted scores) - sum(risk weighted scores)
# > 6   → Favorable
# 2–6   → Conditional
# < 2   → Unfavourable
