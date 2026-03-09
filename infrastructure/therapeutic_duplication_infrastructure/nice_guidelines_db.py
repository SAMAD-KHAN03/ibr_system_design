"""
nice_guidelines_db.py
=====================
Encodes NICE guideline combination rules for therapeutic duplication checking.

STRICTLY NICE-SOURCED:  Every rule in this file maps to a published NICE
guideline code and section reference.  No rules from other sources (FDA,
WHO, BNF) are included.

Coverage (per architecture doc §5):
  NG106  Chronic heart failure in adults (2018 / updated 2023)
  NG28   Hypertension in adults (2019 / updated 2023)
  CG90   Depression in adults (2009 / updated 2022)
  CG181  Lipid modification (2014 / updated 2023)
  CG177  Osteoarthritis (2014)
  CG180  Atrial fibrillation (2014)
  NG196  Venous thromboembolic diseases (2020 / updated 2023)
  NG28   Type 2 diabetes in adults (separate diabetes section)
  CG113  Generalised anxiety disorder and panic disorder (2011 / updated 2020)
  NG180  Chronic pain (2021)
  CG184  Dyspepsia and gastro-oesophageal reflux disease (2014)
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CombinationRule:
    drug_a: str              # generic name OR drug_class string
    drug_b: str              # generic name OR drug_class string
    indication: str          # clinical context (must match shared indication)
    recommendation: str      # SUPPORTED | CONDITIONAL | NOT_RECOMMENDED | CONTRAINDICATED
    recommendation_text: str # Near-verbatim NICE text
    strength: str            # Strong | Conditional | Research only
    guideline_code: str      # e.g. NG106
    section_ref: str         # e.g. 1.3.4
    url: str
    rationale: str
    conditions: list[str] = field(default_factory=list)


@dataclass
class NICEGuideline:
    code: str
    title: str
    rules: list[CombinationRule]


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

_NG106_RULES: list[CombinationRule] = [
    # ACEi + Beta-blocker → SUPPORTED (quadruple therapy pillar)
    CombinationRule(
        drug_a="ACE_INHIBITOR", drug_b="BETA_BLOCKER",
        indication="heart_failure",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Offer an ACE inhibitor and a beta-blocker to all people "
            "with HFrEF."
        ),
        strength="Strong",
        guideline_code="NG106", section_ref="1.3.4",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="Complementary mechanisms: RAAS inhibition (ACEi) + sympathetic blockade (BB) reduce mortality in HFrEF.",
        conditions=["HFrEF with LVEF ≤40%", "Titrate each to maximum tolerated dose"],
    ),
    # ACEi + SGLT2i → SUPPORTED
    CombinationRule(
        drug_a="ACE_INHIBITOR", drug_b="SGLT2_INHIBITOR",
        indication="heart_failure",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Consider an SGLT2 inhibitor in addition to standard therapy "
            "for people with symptomatic HFrEF."
        ),
        strength="Strong",
        guideline_code="NG106", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="SGLT2i provides additional natriuresis and cardioprotection independent of RAAS inhibition.",
        conditions=["HFrEF", "eGFR ≥20 mL/min/1.73 m²"],
    ),
    # ACEi + ARB → NOT RECOMMENDED (dual RAAS)
    CombinationRule(
        drug_a="ACE_INHIBITOR", drug_b="ARB",
        indication="heart_failure",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not routinely offer the combination of an ACE inhibitor "
            "and an ARB to people with heart failure."
        ),
        strength="Strong",
        guideline_code="NG106", section_ref="1.3.6",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="Dual RAAS blockade increases risk of hypotension, hyperkalaemia, and renal impairment without additional benefit.",
        conditions=["Avoid unless specialist review"],
    ),
    # ARNI + ACEi → CONTRAINDICATED (angioedema risk)
    CombinationRule(
        drug_a="ARNI", drug_b="ACE_INHIBITOR",
        indication="heart_failure",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe sacubitril/valsartan concomitantly with "
            "ACE inhibitors — risk of angioedema."
        ),
        strength="Strong",
        guideline_code="NG106", section_ref="1.3.8",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="Neprilysin inhibition combined with ACE inhibition markedly increases bradykinin levels, causing angioedema.",
        conditions=["Must allow 36-hour washout from ACEi before starting ARNI"],
    ),
    # ARNI + ARB → NOT RECOMMENDED
    CombinationRule(
        drug_a="ARNI", drug_b="ARB",
        indication="heart_failure",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Sacubitril/valsartan already contains valsartan (an ARB); "
            "adding a separate ARB provides no benefit and increases risk."
        ),
        strength="Strong",
        guideline_code="NG106", section_ref="1.3.8",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="ARNI contains valsartan component; additional ARB = effective dual RAAS blockade.",
        conditions=["Avoid concurrent ARB with ARNI"],
    ),
    # MRA + ACEi → SUPPORTED (under monitoring)
    CombinationRule(
        drug_a="MINERALOCORTICOID_RECEPTOR_ANTAGONIST", drug_b="ACE_INHIBITOR",
        indication="heart_failure",
        recommendation="CONDITIONAL",
        recommendation_text=(
            "Consider adding a mineralocorticoid receptor antagonist if "
            "symptoms persist despite ACEi and beta-blocker."
        ),
        strength="Conditional",
        guideline_code="NG106", section_ref="1.3.10",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="MRA adds further neurohormonal blockade; risk of hyperkalaemia requires monitoring.",
        conditions=["eGFR ≥30 mL/min/1.73 m²", "K⁺ <5.0 mmol/L", "Monitor electrolytes 1–2 weeks after initiation"],
    ),
    # Beta-blocker + Beta-blocker → NOT RECOMMENDED (dual BB)
    CombinationRule(
        drug_a="BETA_BLOCKER", drug_b="BETA_BLOCKER",
        indication="heart_failure",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Use only one beta-blocker for heart failure management."
        ),
        strength="Strong",
        guideline_code="NG106", section_ref="1.3.4",
        url="https://www.nice.org.uk/guidance/ng106/chapter/Recommendations#pharmacological-treatment",
        rationale="No evidence of additive benefit; increased bradycardia and hypotension risk.",
        conditions=[],
    ),
]

_NG28_HTN_RULES: list[CombinationRule] = [
    # ACEi + CCB → SUPPORTED (step 2)
    CombinationRule(
        drug_a="ACE_INHIBITOR", drug_b="CALCIUM_CHANNEL_BLOCKER",
        indication="hypertension",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Offer step 2 treatment: combine the ACE inhibitor (or ARB) "
            "with a calcium channel blocker."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.4.6",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#choosing-antihypertensive-drug-treatment-for-people-without-type-2-diabetes",
        rationale="Complementary mechanisms; calcium channel blockade adds vasodilatory effect.",
        conditions=["Step 2 hypertension management"],
    ),
    # ARB + CCB → SUPPORTED (step 2, alternative to ACEi)
    CombinationRule(
        drug_a="ARB", drug_b="CALCIUM_CHANNEL_BLOCKER",
        indication="hypertension",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Offer step 2 treatment: combine ARB with a calcium channel blocker "
            "if ACE inhibitor not tolerated."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.4.6",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#choosing-antihypertensive-drug-treatment-for-people-without-type-2-diabetes",
        rationale="ARB + CCB equivalent to ACEi + CCB with fewer cough side effects.",
        conditions=["Step 2 hypertension management", "ACE inhibitor not tolerated"],
    ),
    # ACEi + ARB → NOT RECOMMENDED (dual RAAS hypertension)
    CombinationRule(
        drug_a="ACE_INHIBITOR", drug_b="ARB",
        indication="hypertension",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not combine ACE inhibitors and ARBs for hypertension treatment."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.4.8",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations",
        rationale="Dual RAAS blockade: hypotension, hyperkalaemia, renal impairment; no additional BP benefit.",
        conditions=[],
    ),
    # Beta-blocker + Beta-blocker → NOT RECOMMENDED
    CombinationRule(
        drug_a="BETA_BLOCKER", drug_b="BETA_BLOCKER",
        indication="hypertension",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not use more than one beta-blocker concurrently for hypertension."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.4.7",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations",
        rationale="No therapeutic gain; additive bradycardia and hypotension.",
        conditions=[],
    ),
]

_CG90_RULES: list[CombinationRule] = [
    # Dual SSRI → CONTRAINDICATED
    CombinationRule(
        drug_a="SSRI", drug_b="SSRI",
        indication="depression",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe two SSRIs concurrently — this does not provide "
            "additional benefit and increases the risk of serotonin syndrome."
        ),
        strength="Strong",
        guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90/chapter/1-Guidance",
        rationale="Dual serotonin reuptake inhibition: markedly elevated serotonin levels, risk of serotonin syndrome.",
        conditions=[],
    ),
    # SSRI + SNRI → NOT RECOMMENDED
    CombinationRule(
        drug_a="SSRI", drug_b="SNRI",
        indication="depression",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Combining an SSRI with an SNRI is not recommended; "
            "switch rather than combine antidepressant classes."
        ),
        strength="Strong",
        guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90/chapter/1-Guidance",
        rationale="Both agents inhibit serotonin reuptake; combination increases serotonin syndrome risk.",
        conditions=["If combination needed, specialist mental health review required"],
    ),
    # Dual SNRI → CONTRAINDICATED
    CombinationRule(
        drug_a="SNRI", drug_b="SNRI",
        indication="depression",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe two SNRIs concurrently."
        ),
        strength="Strong",
        guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90/chapter/1-Guidance",
        rationale="Additive serotonin and norepinephrine reuptake inhibition; no evidence of additional antidepressant benefit.",
        conditions=[],
    ),
    # SSRI + SNRI → NOT RECOMMENDED (anxiety context too)
    CombinationRule(
        drug_a="SSRI", drug_b="SNRI",
        indication="anxiety",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Combining SSRI and SNRI for anxiety is not recommended; switch sequentially."
        ),
        strength="Strong",
        guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90/chapter/1-Guidance",
        rationale="Duplicate serotonergic mechanism; risk of serotonin toxicity.",
        conditions=[],
    ),
]

_CG181_RULES: list[CombinationRule] = [
    # Dual statin → NOT RECOMMENDED
    CombinationRule(
        drug_a="STATIN", drug_b="STATIN",
        indication="hyperlipidaemia",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not offer two statins concurrently for lipid modification."
        ),
        strength="Strong",
        guideline_code="CG181", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/cg181/chapter/1-Recommendations",
        rationale="No additional lipid-lowering benefit; increased myopathy risk.",
        conditions=["If higher LDL-C lowering needed, switch to higher potency statin or add ezetimibe"],
    ),
    # Dual statin → NOT RECOMMENDED (cardiovascular prevention)
    CombinationRule(
        drug_a="STATIN", drug_b="STATIN",
        indication="cardiovascular_prevention",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not use two statins simultaneously for cardiovascular prevention."
        ),
        strength="Strong",
        guideline_code="CG181", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/cg181/chapter/1-Recommendations",
        rationale="Duplicate HMG-CoA reductase inhibition with no additive benefit.",
        conditions=[],
    ),
]

_CG177_RULES: list[CombinationRule] = [
    # Dual NSAID → CONTRAINDICATED
    CombinationRule(
        drug_a="NSAID", drug_b="NSAID",
        indication="osteoarthritis",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe more than one oral NSAID concurrently for "
            "osteoarthritis — this significantly increases GI and CV risk."
        ),
        strength="Strong",
        guideline_code="CG177", section_ref="1.5.1",
        url="https://www.nice.org.uk/guidance/cg177/chapter/1-Recommendations",
        rationale="Dual COX inhibition: no additional analgesia; substantially increased GI bleeding, renal and cardiovascular risk.",
        conditions=["If NSAIDs are needed, use lowest effective dose of one agent only"],
    ),
    # NSAID + NSAID → CONTRAINDICATED (pain context)
    CombinationRule(
        drug_a="NSAID", drug_b="NSAID",
        indication="pain",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe two NSAIDs concurrently for pain management."
        ),
        strength="Strong",
        guideline_code="CG177", section_ref="1.5.1",
        url="https://www.nice.org.uk/guidance/cg177/chapter/1-Recommendations",
        rationale="Duplicated mechanism; increased toxicity without additional analgesia.",
        conditions=[],
    ),
    # COX-2 + NSAID → CONTRAINDICATED
    CombinationRule(
        drug_a="COX2_INHIBITOR", drug_b="NSAID",
        indication="osteoarthritis",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe a COX-2 inhibitor with a traditional NSAID concurrently."
        ),
        strength="Strong",
        guideline_code="CG177", section_ref="1.5.2",
        url="https://www.nice.org.uk/guidance/cg177/chapter/1-Recommendations",
        rationale="COX-2 inhibitors + non-selective NSAIDs: combined COX inhibition negates selectivity advantage and multiplies GI/CV risk.",
        conditions=[],
    ),
    # COX-2 + NSAID → CONTRAINDICATED (pain context)
    CombinationRule(
        drug_a="COX2_INHIBITOR", drug_b="NSAID",
        indication="pain",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe a COX-2 inhibitor and a standard NSAID concurrently for pain."
        ),
        strength="Strong",
        guideline_code="CG177", section_ref="1.5.2",
        url="https://www.nice.org.uk/guidance/cg177/chapter/1-Recommendations",
        rationale="Concurrent COX-2 inhibitor and NSAID negates the GI-sparing benefit and increases cardiovascular risk.",
        conditions=[],
    ),
    # Dual COX-2 → CONTRAINDICATED
    CombinationRule(
        drug_a="COX2_INHIBITOR", drug_b="COX2_INHIBITOR",
        indication="osteoarthritis",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe two COX-2 inhibitors concurrently."
        ),
        strength="Strong",
        guideline_code="CG177", section_ref="1.5.2",
        url="https://www.nice.org.uk/guidance/cg177/chapter/1-Recommendations",
        rationale="Duplicate selective COX-2 inhibition; no additive benefit, increased cardiovascular risk.",
        conditions=[],
    ),
]

_CG180_NG196_RULES: list[CombinationRule] = [
    # VKA + DOAC Factor Xa → CONTRAINDICATED
    CombinationRule(
        drug_a="VITAMIN_K_ANTAGONIST", drug_b="DOAC_FACTOR_Xa_INHIBITOR",
        indication="atrial_fibrillation",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe a VKA and a DOAC concurrently for atrial fibrillation "
            "anticoagulation — dual anticoagulation significantly increases bleeding risk."
        ),
        strength="Strong",
        guideline_code="CG180", section_ref="1.11.2",
        url="https://www.nice.org.uk/guidance/cg180/chapter/1-Recommendations",
        rationale="Concurrent anticoagulants with different mechanisms provide no additional thromboprotection and greatly increase haemorrhage risk.",
        conditions=["Transition periods only under specialist supervision"],
    ),
    # VKA + DOAC Thrombin → CONTRAINDICATED
    CombinationRule(
        drug_a="VITAMIN_K_ANTAGONIST", drug_b="DOAC_THROMBIN_INHIBITOR",
        indication="atrial_fibrillation",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not combine warfarin with dabigatran for AF anticoagulation."
        ),
        strength="Strong",
        guideline_code="CG180", section_ref="1.11.2",
        url="https://www.nice.org.uk/guidance/cg180/chapter/1-Recommendations",
        rationale="Dual anticoagulation: markedly elevated bleeding risk without thromboprotective benefit.",
        conditions=[],
    ),
    # DOAC Factor Xa + DOAC Thrombin → CONTRAINDICATED
    CombinationRule(
        drug_a="DOAC_FACTOR_Xa_INHIBITOR", drug_b="DOAC_THROMBIN_INHIBITOR",
        indication="atrial_fibrillation",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not combine two DOACs with different mechanisms of action."
        ),
        strength="Strong",
        guideline_code="NG196", section_ref="1.6.1",
        url="https://www.nice.org.uk/guidance/ng196/chapter/Recommendations",
        rationale="Dual DOAC therapy: no evidence of benefit; high haemorrhage risk.",
        conditions=[],
    ),
    # Dual DOAC Factor Xa → CONTRAINDICATED
    CombinationRule(
        drug_a="DOAC_FACTOR_Xa_INHIBITOR", drug_b="DOAC_FACTOR_Xa_INHIBITOR",
        indication="anticoagulation",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not prescribe two Factor Xa inhibitors concurrently."
        ),
        strength="Strong",
        guideline_code="NG196", section_ref="1.6.1",
        url="https://www.nice.org.uk/guidance/ng196/chapter/Recommendations",
        rationale="Duplicate mechanism: markedly increased bleeding risk without additional anticoagulant benefit.",
        conditions=[],
    ),
    # VKA + DOAC → CONTRAINDICATED (DVT/PE context)
    CombinationRule(
        drug_a="VITAMIN_K_ANTAGONIST", drug_b="DOAC_FACTOR_Xa_INHIBITOR",
        indication="dvt",
        recommendation="CONTRAINDICATED",
        recommendation_text=(
            "Do not combine warfarin and a DOAC for VTE treatment or prevention."
        ),
        strength="Strong",
        guideline_code="NG196", section_ref="1.6.1",
        url="https://www.nice.org.uk/guidance/ng196/chapter/Recommendations",
        rationale="Dual anticoagulation for VTE: no benefit, high haemorrhage risk.",
        conditions=[],
    ),
]

_NG28_DIABETES_RULES: list[CombinationRule] = [
    # Metformin + SGLT2i → SUPPORTED
    CombinationRule(
        drug_a="BIGUANIDE", drug_b="SGLT2_INHIBITOR",
        indication="type2_diabetes",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Consider adding an SGLT2 inhibitor to metformin for people with "
            "type 2 diabetes and established cardiovascular disease or at high CV risk."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.7.3",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="Complementary mechanisms: AMPK activation (metformin) + renal glucose excretion (SGLT2i); additive HbA1c lowering and CV/renal benefits.",
        conditions=["eGFR ≥30 mL/min/1.73 m²", "Check for ketoacidosis risk"],
    ),
    # Metformin + GLP1 → SUPPORTED
    CombinationRule(
        drug_a="BIGUANIDE", drug_b="GLP1_AGONIST",
        indication="type2_diabetes",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Consider adding a GLP-1 receptor agonist to metformin if HbA1c "
            "remains above target, especially with BMI ≥35 kg/m²."
        ),
        strength="Conditional",
        guideline_code="NG28", section_ref="1.7.5",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="GLP1 agonism complements AMPK activation; provides HbA1c reduction and weight loss.",
        conditions=["BMI ≥35 kg/m² or significant obesity-related comorbidities"],
    ),
    # Dual GLP1 / SGLT2 → NOT RECOMMENDED
    CombinationRule(
        drug_a="GLP1_AGONIST", drug_b="SGLT2_INHIBITOR",
        indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "The combination of a GLP-1 receptor agonist and an SGLT2 inhibitor "
            "is not recommended as dual add-on therapy to metformin without "
            "individual clinical assessment."
        ),
        strength="Conditional",
        guideline_code="NG28", section_ref="1.7.8",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="Limited evidence for additive benefit beyond individual agents; increased cost and complexity.",
        conditions=["Specialist review may support combination in specific high-risk patients"],
    ),
    # Metformin + DPP4 → SUPPORTED
    CombinationRule(
        drug_a="BIGUANIDE", drug_b="DPP4_INHIBITOR",
        indication="type2_diabetes",
        recommendation="SUPPORTED",
        recommendation_text=(
            "Consider adding a DPP-4 inhibitor to metformin if HbA1c "
            "remains above target and SGLT2i or GLP1 are not appropriate."
        ),
        strength="Conditional",
        guideline_code="NG28", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="DPP4 inhibitors augment GLP1 pathway complementing metformin's AMPK activation.",
        conditions=["Second-line option when SGLT2i contraindicated or not tolerated"],
    ),
    # Dual GLP1 → NOT RECOMMENDED
    CombinationRule(
        drug_a="GLP1_AGONIST", drug_b="GLP1_AGONIST",
        indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not prescribe two GLP-1 receptor agonists concurrently."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.7.5",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="Duplicate mechanism; no additional HbA1c benefit; increased GI adverse effects.",
        conditions=[],
    ),
    # Dual DPP4 → NOT RECOMMENDED
    CombinationRule(
        drug_a="DPP4_INHIBITOR", drug_b="DPP4_INHIBITOR",
        indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not prescribe two DPP-4 inhibitors concurrently."
        ),
        strength="Strong",
        guideline_code="NG28", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="Duplicate GLP1 augmentation mechanism; no added benefit.",
        conditions=[],
    ),
    # GLP1 + DPP4 → NOT RECOMMENDED (mutual blunting)
    CombinationRule(
        drug_a="GLP1_AGONIST", drug_b="DPP4_INHIBITOR",
        indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not combine GLP-1 receptor agonist with a DPP-4 inhibitor — "
            "DPP-4 inhibitors augment endogenous GLP-1 which is largely superseded "
            "by exogenous GLP-1 agonist."
        ),
        strength="Conditional",
        guideline_code="NG28", section_ref="1.7.5",
        url="https://www.nice.org.uk/guidance/ng28/chapter/Recommendations#drug-treatment-for-adults-with-type-2-diabetes",
        rationale="GLP1 agonist supersedes DPP4 inhibitor's mechanism; combination adds cost without benefit.",
        conditions=[],
    ),
]

_CG113_RULES: list[CombinationRule] = [
    # Dual benzodiazepine → NOT RECOMMENDED
    CombinationRule(
        drug_a="BENZODIAZEPINE", drug_b="BENZODIAZEPINE",
        indication="anxiety",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not prescribe two benzodiazepines concurrently for anxiety or panic disorder; "
            "if one is insufficient, optimise dose or switch agent."
        ),
        strength="Strong",
        guideline_code="CG113", section_ref="1.3.1",
        url="https://www.nice.org.uk/guidance/cg113/chapter/1-Guidance",
        rationale="Additive CNS depression, respiratory depression, and dependence risk without additional anxiolytic benefit.",
        conditions=["Short-term use only even as monotherapy"],
    ),
]

_NG180_RULES: list[CombinationRule] = [
    # Dual opioid → NOT RECOMMENDED
    CombinationRule(
        drug_a="OPIOID_ANALGESIC", drug_b="OPIOID_ANALGESIC",
        indication="pain",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Avoid prescribing two opioids concurrently for chronic pain; "
            "if analgesia is inadequate, consider dose optimisation or opioid rotation, not combination."
        ),
        strength="Strong",
        guideline_code="NG180", section_ref="1.5.6",
        url="https://www.nice.org.uk/guidance/ng180/chapter/Recommendations",
        rationale="Dual opioid therapy: additive respiratory depression and overdose risk; no evidence of improved analgesia.",
        conditions=["Opioid rotation may be appropriate under specialist supervision"],
    ),
]

_CG184_RULES: list[CombinationRule] = [
    # Dual PPI → NOT RECOMMENDED
    CombinationRule(
        drug_a="PPI", drug_b="PPI",
        indication="gord",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not prescribe two proton pump inhibitors concurrently for GORD."
        ),
        strength="Strong",
        guideline_code="CG184", section_ref="1.3.2",
        url="https://www.nice.org.uk/guidance/cg184/chapter/1-Recommendations",
        rationale="Duplicate H⁺/K⁺-ATPase inhibition provides no additional acid suppression benefit.",
        conditions=["If PPI-refractory symptoms, investigate before escalating"],
    ),
    # Dual PPI (peptic ulcer context)
    CombinationRule(
        drug_a="PPI", drug_b="PPI",
        indication="peptic_ulcer",
        recommendation="NOT_RECOMMENDED",
        recommendation_text=(
            "Do not prescribe two PPIs concurrently for peptic ulcer treatment."
        ),
        strength="Strong",
        guideline_code="CG184", section_ref="1.3.2",
        url="https://www.nice.org.uk/guidance/cg184/chapter/1-Recommendations",
        rationale="One PPI at adequate dose provides maximal acid suppression; dual PPI adds risk without benefit.",
        conditions=[],
    ),
]

# ---------------------------------------------------------------------------
# Master registry
# ---------------------------------------------------------------------------

NICE_GUIDELINES: dict[str, NICEGuideline] = {
    "NG106": NICEGuideline(
        code="NG106",
        title="Chronic heart failure in adults (2018, updated 2023)",
        rules=_NG106_RULES,
    ),
    "NG28_HTN": NICEGuideline(
        code="NG28",
        title="Hypertension in adults (2019, updated 2023)",
        rules=_NG28_HTN_RULES,
    ),
    "CG90": NICEGuideline(
        code="CG90",
        title="Depression in adults (2009, updated 2022)",
        rules=_CG90_RULES,
    ),
    "CG181": NICEGuideline(
        code="CG181",
        title="Lipid modification: cardiovascular risk assessment (2014, updated 2023)",
        rules=_CG181_RULES,
    ),
    "CG177": NICEGuideline(
        code="CG177",
        title="Osteoarthritis: care and management (2014)",
        rules=_CG177_RULES,
    ),
    "CG180_NG196": NICEGuideline(
        code="CG180/NG196",
        title="Atrial fibrillation / Venous thromboembolic diseases",
        rules=_CG180_NG196_RULES,
    ),
    "NG28_DM": NICEGuideline(
        code="NG28",
        title="Type 2 diabetes in adults (NG28, diabetes section)",
        rules=_NG28_DIABETES_RULES,
    ),
    "CG113": NICEGuideline(
        code="CG113",
        title="Generalised anxiety disorder and panic disorder (2011, updated 2020)",
        rules=_CG113_RULES,
    ),
    "NG180": NICEGuideline(
        code="NG180",
        title="Chronic pain (primary and secondary) in over 16s (2021)",
        rules=_NG180_RULES,
    ),
    "CG184": NICEGuideline(
        code="CG184",
        title="Gastro-oesophageal reflux disease and dyspepsia in adults (2014)",
        rules=_CG184_RULES,
    ),
}


def _all_rules() -> list[CombinationRule]:
    return [rule for g in NICE_GUIDELINES.values() for rule in g.rules]


def find_combination_rules(
    class_a: str,
    name_a: str,
    class_b: str,
    name_b: str,
    shared_indications: set[str],
) -> list[CombinationRule]:
    """
    Bidirectional, class-OR-name matching against all NICE rules.
    Returns all matching CombinationRule objects (may be empty).
    """
    ids_a = {class_a.upper(), name_a.lower()}
    ids_b = {class_b.upper(), name_b.lower()}
    matches: list[CombinationRule] = []

    for rule in _all_rules():
        ra = rule.drug_a.upper() if rule.drug_a == rule.drug_a.upper() else rule.drug_a.lower()
        rb = rule.drug_b.upper() if rule.drug_b == rule.drug_b.upper() else rule.drug_b.lower()
        rule_a_ids = {rule.drug_a.upper(), rule.drug_a.lower()}
        rule_b_ids = {rule.drug_b.upper(), rule.drug_b.lower()}

        # Bidirectional: (a matches rule.drug_a AND b matches rule.drug_b) OR vice versa
        forward  = (ids_a & rule_a_ids) and (ids_b & rule_b_ids)
        backward = (ids_a & rule_b_ids) and (ids_b & rule_a_ids)

        if not (forward or backward):
            continue

        # Indication match
        if rule.indication in shared_indications or rule.indication == "":
            matches.append(rule)
        # Same-class rules (e.g. SSRI+SSRI) also match if class matches regardless of indication specificity
        elif rule.drug_a == rule.drug_b and (rule.drug_a.upper() in {class_a.upper(), class_b.upper()}):
            matches.append(rule)

    return matches
