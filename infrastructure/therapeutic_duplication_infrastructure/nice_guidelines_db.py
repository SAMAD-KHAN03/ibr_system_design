"""
nice_guidelines_db.py
=====================
Encodes NICE guideline combination rules for therapeutic duplication checking.

STRICTLY NICE-SOURCED: Every rule maps to a published NICE guideline code
and section reference. No rules from FDA, WHO, or BNF are included.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CombinationRule:
    drug_a: str
    drug_b: str
    indication: str
    recommendation: str        # SUPPORTED | CONDITIONAL | NOT_RECOMMENDED | CONTRAINDICATED
    recommendation_text: str
    strength: str
    guideline_code: str
    section_ref: str
    url: str
    rationale: str
    conditions: list[str] = field(default_factory=list)


@dataclass
class NICEGuideline:
    code: str
    title: str
    rules: list[CombinationRule]


_NG106_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="ACE_INHIBITOR", drug_b="BETA_BLOCKER", indication="heart_failure",
        recommendation="SUPPORTED",
        recommendation_text="Offer an ACE inhibitor and a beta-blocker to all people with HFrEF.",
        strength="Strong", guideline_code="NG106", section_ref="1.3.4",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="Complementary mechanisms: RAAS inhibition + sympathetic blockade reduce mortality in HFrEF.",
        conditions=["HFrEF with LVEF ≤40%", "Titrate each to maximum tolerated dose"]),
    CombinationRule(drug_a="ACE_INHIBITOR", drug_b="SGLT2_INHIBITOR", indication="heart_failure",
        recommendation="SUPPORTED",
        recommendation_text="Consider an SGLT2 inhibitor in addition to standard therapy for symptomatic HFrEF.",
        strength="Strong", guideline_code="NG106", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="SGLT2i provides additional natriuresis and cardioprotection independent of RAAS inhibition.",
        conditions=["HFrEF", "eGFR ≥20 mL/min/1.73 m²"]),
    CombinationRule(drug_a="ACE_INHIBITOR", drug_b="ARB", indication="heart_failure",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not routinely offer the combination of an ACE inhibitor and an ARB to people with heart failure.",
        strength="Strong", guideline_code="NG106", section_ref="1.3.6",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="Dual RAAS blockade increases risk of hypotension, hyperkalaemia, and renal impairment without benefit.",
        conditions=["Avoid unless specialist review"]),
    CombinationRule(drug_a="ARNI", drug_b="ACE_INHIBITOR", indication="heart_failure",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe sacubitril/valsartan concomitantly with ACE inhibitors — risk of angioedema.",
        strength="Strong", guideline_code="NG106", section_ref="1.3.8",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="Neprilysin + ACE inhibition markedly increases bradykinin levels, causing angioedema.",
        conditions=["Must allow 36-hour washout from ACEi before starting ARNI"]),
    CombinationRule(drug_a="ARNI", drug_b="ARB", indication="heart_failure",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Sacubitril/valsartan already contains valsartan; adding a separate ARB provides no benefit and increases risk.",
        strength="Strong", guideline_code="NG106", section_ref="1.3.8",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="ARNI contains valsartan component; additional ARB = effective dual RAAS blockade.",
        conditions=["Avoid concurrent ARB with ARNI"]),
    CombinationRule(drug_a="MINERALOCORTICOID_RECEPTOR_ANTAGONIST", drug_b="ACE_INHIBITOR", indication="heart_failure",
        recommendation="CONDITIONAL",
        recommendation_text="Consider adding an MRA if symptoms persist despite ACEi and beta-blocker.",
        strength="Conditional", guideline_code="NG106", section_ref="1.3.10",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="MRA adds further neurohormonal blockade; risk of hyperkalaemia requires monitoring.",
        conditions=["eGFR ≥30 mL/min/1.73 m²", "K⁺ <5.0 mmol/L", "Monitor electrolytes 1–2 weeks after initiation"]),
    CombinationRule(drug_a="BETA_BLOCKER", drug_b="BETA_BLOCKER", indication="heart_failure",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Use only one beta-blocker for heart failure management.",
        strength="Strong", guideline_code="NG106", section_ref="1.3.4",
        url="https://www.nice.org.uk/guidance/ng106",
        rationale="No additive benefit; increased bradycardia and hypotension risk.",
        conditions=[]),
]

_NG28_HTN_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="ACE_INHIBITOR", drug_b="CALCIUM_CHANNEL_BLOCKER", indication="hypertension",
        recommendation="SUPPORTED",
        recommendation_text="Offer step 2 treatment: combine ACE inhibitor with a calcium channel blocker.",
        strength="Strong", guideline_code="NG28", section_ref="1.4.6",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="Complementary mechanisms; CCB adds vasodilatory effect.",
        conditions=["Step 2 hypertension management"]),
    CombinationRule(drug_a="ARB", drug_b="CALCIUM_CHANNEL_BLOCKER", indication="hypertension",
        recommendation="SUPPORTED",
        recommendation_text="Offer step 2 treatment: combine ARB with a calcium channel blocker if ACEi not tolerated.",
        strength="Strong", guideline_code="NG28", section_ref="1.4.6",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="ARB + CCB equivalent to ACEi + CCB with fewer cough side effects.",
        conditions=["Step 2 hypertension management", "ACE inhibitor not tolerated"]),
    CombinationRule(drug_a="ACE_INHIBITOR", drug_b="ARB", indication="hypertension",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not combine ACE inhibitors and ARBs for hypertension treatment.",
        strength="Strong", guideline_code="NG28", section_ref="1.4.8",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="Dual RAAS blockade: hypotension, hyperkalaemia, renal impairment; no additional BP benefit.",
        conditions=[]),
    CombinationRule(drug_a="BETA_BLOCKER", drug_b="BETA_BLOCKER", indication="hypertension",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not use more than one beta-blocker concurrently for hypertension.",
        strength="Strong", guideline_code="NG28", section_ref="1.4.7",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="No therapeutic gain; additive bradycardia and hypotension.",
        conditions=[]),
]

_CG90_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="SSRI", drug_b="SSRI", indication="depression",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe two SSRIs concurrently — risk of serotonin syndrome.",
        strength="Strong", guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90",
        rationale="Dual serotonin reuptake inhibition: markedly elevated serotonin, risk of serotonin syndrome.",
        conditions=[]),
    CombinationRule(drug_a="SSRI", drug_b="SNRI", indication="depression",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Combining an SSRI with an SNRI is not recommended; switch rather than combine.",
        strength="Strong", guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90",
        rationale="Both agents inhibit serotonin reuptake; increased serotonin syndrome risk.",
        conditions=["If combination needed, specialist mental health review required"]),
    CombinationRule(drug_a="SNRI", drug_b="SNRI", indication="depression",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe two SNRIs concurrently.",
        strength="Strong", guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90",
        rationale="Additive serotonin and norepinephrine reuptake inhibition; no additional benefit.",
        conditions=[]),
    CombinationRule(drug_a="SSRI", drug_b="SNRI", indication="anxiety",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Combining SSRI and SNRI for anxiety is not recommended; switch sequentially.",
        strength="Strong", guideline_code="CG90", section_ref="1.3.5",
        url="https://www.nice.org.uk/guidance/cg90",
        rationale="Duplicate serotonergic mechanism; risk of serotonin toxicity.",
        conditions=[]),
]

_CG181_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="STATIN", drug_b="STATIN", indication="hyperlipidaemia",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not offer two statins concurrently for lipid modification.",
        strength="Strong", guideline_code="CG181", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/cg181",
        rationale="No additional lipid-lowering benefit; increased myopathy risk.",
        conditions=["Switch to higher potency statin or add ezetimibe if needed"]),
    CombinationRule(drug_a="STATIN", drug_b="STATIN", indication="cardiovascular_prevention",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not use two statins simultaneously for cardiovascular prevention.",
        strength="Strong", guideline_code="CG181", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/cg181",
        rationale="Duplicate HMG-CoA reductase inhibition with no additive benefit.",
        conditions=[]),
]

_CG177_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="NSAID", drug_b="NSAID", indication="osteoarthritis",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe more than one oral NSAID concurrently for osteoarthritis.",
        strength="Strong", guideline_code="CG177", section_ref="1.5.1",
        url="https://www.nice.org.uk/guidance/cg177",
        rationale="Dual COX inhibition: no additional analgesia; increased GI bleeding, renal and CV risk.",
        conditions=["Use lowest effective dose of one agent only"]),
    CombinationRule(drug_a="NSAID", drug_b="NSAID", indication="pain",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe two NSAIDs concurrently for pain management.",
        strength="Strong", guideline_code="CG177", section_ref="1.5.1",
        url="https://www.nice.org.uk/guidance/cg177",
        rationale="Duplicated mechanism; increased toxicity without additional analgesia.",
        conditions=[]),
    CombinationRule(drug_a="COX2_INHIBITOR", drug_b="NSAID", indication="osteoarthritis",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe a COX-2 inhibitor with a traditional NSAID concurrently.",
        strength="Strong", guideline_code="CG177", section_ref="1.5.2",
        url="https://www.nice.org.uk/guidance/cg177",
        rationale="Combined COX inhibition negates selectivity advantage and multiplies GI/CV risk.",
        conditions=[]),
    CombinationRule(drug_a="COX2_INHIBITOR", drug_b="NSAID", indication="pain",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe a COX-2 inhibitor and a standard NSAID concurrently for pain.",
        strength="Strong", guideline_code="CG177", section_ref="1.5.2",
        url="https://www.nice.org.uk/guidance/cg177",
        rationale="Concurrent COX-2 inhibitor and NSAID negates GI-sparing benefit and increases CV risk.",
        conditions=[]),
    CombinationRule(drug_a="COX2_INHIBITOR", drug_b="COX2_INHIBITOR", indication="osteoarthritis",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe two COX-2 inhibitors concurrently.",
        strength="Strong", guideline_code="CG177", section_ref="1.5.2",
        url="https://www.nice.org.uk/guidance/cg177",
        rationale="Duplicate selective COX-2 inhibition; increased cardiovascular risk.",
        conditions=[]),
]

_CG180_NG196_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="VITAMIN_K_ANTAGONIST", drug_b="DOAC_FACTOR_Xa_INHIBITOR", indication="atrial_fibrillation",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe a VKA and a DOAC concurrently for AF anticoagulation.",
        strength="Strong", guideline_code="CG180", section_ref="1.11.2",
        url="https://www.nice.org.uk/guidance/cg180",
        rationale="Dual anticoagulants: no additional thromboprotection, greatly increased haemorrhage risk.",
        conditions=["Transition periods only under specialist supervision"]),
    CombinationRule(drug_a="VITAMIN_K_ANTAGONIST", drug_b="DOAC_THROMBIN_INHIBITOR", indication="atrial_fibrillation",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not combine warfarin with dabigatran for AF anticoagulation.",
        strength="Strong", guideline_code="CG180", section_ref="1.11.2",
        url="https://www.nice.org.uk/guidance/cg180",
        rationale="Dual anticoagulation: markedly elevated bleeding risk without thromboprotective benefit.",
        conditions=[]),
    CombinationRule(drug_a="DOAC_FACTOR_Xa_INHIBITOR", drug_b="DOAC_THROMBIN_INHIBITOR", indication="atrial_fibrillation",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not combine two DOACs with different mechanisms of action.",
        strength="Strong", guideline_code="NG196", section_ref="1.6.1",
        url="https://www.nice.org.uk/guidance/ng196",
        rationale="Dual DOAC therapy: no evidence of benefit; high haemorrhage risk.",
        conditions=[]),
    CombinationRule(drug_a="DOAC_FACTOR_Xa_INHIBITOR", drug_b="DOAC_FACTOR_Xa_INHIBITOR", indication="anticoagulation",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not prescribe two Factor Xa inhibitors concurrently.",
        strength="Strong", guideline_code="NG196", section_ref="1.6.1",
        url="https://www.nice.org.uk/guidance/ng196",
        rationale="Duplicate mechanism: markedly increased bleeding risk without additional benefit.",
        conditions=[]),
    CombinationRule(drug_a="VITAMIN_K_ANTAGONIST", drug_b="DOAC_FACTOR_Xa_INHIBITOR", indication="dvt",
        recommendation="CONTRAINDICATED",
        recommendation_text="Do not combine warfarin and a DOAC for VTE treatment or prevention.",
        strength="Strong", guideline_code="NG196", section_ref="1.6.1",
        url="https://www.nice.org.uk/guidance/ng196",
        rationale="Dual anticoagulation for VTE: no benefit, high haemorrhage risk.",
        conditions=[]),
]

_NG28_DIABETES_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="BIGUANIDE", drug_b="SGLT2_INHIBITOR", indication="type2_diabetes",
        recommendation="SUPPORTED",
        recommendation_text="Consider adding an SGLT2 inhibitor to metformin for people with T2DM and established CVD or high CV risk.",
        strength="Strong", guideline_code="NG28", section_ref="1.7.3",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="Complementary mechanisms; additive HbA1c lowering and CV/renal benefits.",
        conditions=["eGFR ≥30 mL/min/1.73 m²", "Check for ketoacidosis risk"]),
    CombinationRule(drug_a="BIGUANIDE", drug_b="GLP1_AGONIST", indication="type2_diabetes",
        recommendation="SUPPORTED",
        recommendation_text="Consider adding a GLP-1 receptor agonist to metformin if HbA1c remains above target.",
        strength="Conditional", guideline_code="NG28", section_ref="1.7.5",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="GLP1 agonism complements AMPK activation; provides HbA1c reduction and weight loss.",
        conditions=["BMI ≥35 kg/m² or significant obesity-related comorbidities"]),
    CombinationRule(drug_a="GLP1_AGONIST", drug_b="SGLT2_INHIBITOR", indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="GLP-1 agonist + SGLT2 inhibitor as dual add-on not recommended without individual clinical assessment.",
        strength="Conditional", guideline_code="NG28", section_ref="1.7.8",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="Limited evidence for additive benefit; increased cost and complexity.",
        conditions=["Specialist review may support in specific high-risk patients"]),
    CombinationRule(drug_a="BIGUANIDE", drug_b="DPP4_INHIBITOR", indication="type2_diabetes",
        recommendation="SUPPORTED",
        recommendation_text="Consider adding a DPP-4 inhibitor to metformin if HbA1c remains above target and SGLT2i/GLP1 not appropriate.",
        strength="Conditional", guideline_code="NG28", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="DPP4 inhibitors augment GLP1 pathway complementing metformin's AMPK activation.",
        conditions=["Second-line option when SGLT2i contraindicated or not tolerated"]),
    CombinationRule(drug_a="GLP1_AGONIST", drug_b="GLP1_AGONIST", indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not prescribe two GLP-1 receptor agonists concurrently.",
        strength="Strong", guideline_code="NG28", section_ref="1.7.5",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="Duplicate mechanism; no additional HbA1c benefit; increased GI adverse effects.",
        conditions=[]),
    CombinationRule(drug_a="DPP4_INHIBITOR", drug_b="DPP4_INHIBITOR", indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not prescribe two DPP-4 inhibitors concurrently.",
        strength="Strong", guideline_code="NG28", section_ref="1.7.4",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="Duplicate GLP1 augmentation mechanism; no added benefit.",
        conditions=[]),
    CombinationRule(drug_a="GLP1_AGONIST", drug_b="DPP4_INHIBITOR", indication="type2_diabetes",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not combine GLP-1 receptor agonist with a DPP-4 inhibitor.",
        strength="Conditional", guideline_code="NG28", section_ref="1.7.5",
        url="https://www.nice.org.uk/guidance/ng28",
        rationale="GLP1 agonist supersedes DPP4 inhibitor's mechanism; combination adds cost without benefit.",
        conditions=[]),
]

_CG113_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="BENZODIAZEPINE", drug_b="BENZODIAZEPINE", indication="anxiety",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not prescribe two benzodiazepines concurrently for anxiety or panic disorder.",
        strength="Strong", guideline_code="CG113", section_ref="1.3.1",
        url="https://www.nice.org.uk/guidance/cg113",
        rationale="Additive CNS depression, respiratory depression, and dependence risk without additional anxiolytic benefit.",
        conditions=["Short-term use only even as monotherapy"]),
]

_NG180_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="OPIOID_ANALGESIC", drug_b="OPIOID_ANALGESIC", indication="pain",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Avoid prescribing two opioids concurrently for chronic pain.",
        strength="Strong", guideline_code="NG180", section_ref="1.5.6",
        url="https://www.nice.org.uk/guidance/ng180",
        rationale="Dual opioid therapy: additive respiratory depression and overdose risk; no improved analgesia.",
        conditions=["Opioid rotation may be appropriate under specialist supervision"]),
]

_CG184_RULES: list[CombinationRule] = [
    CombinationRule(drug_a="PPI", drug_b="PPI", indication="gord",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not prescribe two proton pump inhibitors concurrently for GORD.",
        strength="Strong", guideline_code="CG184", section_ref="1.3.2",
        url="https://www.nice.org.uk/guidance/cg184",
        rationale="Duplicate H⁺/K⁺-ATPase inhibition provides no additional acid suppression benefit.",
        conditions=["If PPI-refractory symptoms, investigate before escalating"]),
    CombinationRule(drug_a="PPI", drug_b="PPI", indication="peptic_ulcer",
        recommendation="NOT_RECOMMENDED",
        recommendation_text="Do not prescribe two PPIs concurrently for peptic ulcer treatment.",
        strength="Strong", guideline_code="CG184", section_ref="1.3.2",
        url="https://www.nice.org.uk/guidance/cg184",
        rationale="One PPI at adequate dose provides maximal acid suppression.",
        conditions=[]),
]

NICE_GUIDELINES: dict[str, NICEGuideline] = {
    "NG106":       NICEGuideline("NG106",    "Chronic heart failure in adults",             _NG106_RULES),
    "NG28_HTN":    NICEGuideline("NG28",     "Hypertension in adults",                      _NG28_HTN_RULES),
    "CG90":        NICEGuideline("CG90",     "Depression in adults",                        _CG90_RULES),
    "CG181":       NICEGuideline("CG181",    "Lipid modification",                          _CG181_RULES),
    "CG177":       NICEGuideline("CG177",    "Osteoarthritis",                              _CG177_RULES),
    "CG180_NG196": NICEGuideline("CG180/NG196", "AF / Venous thromboembolic diseases",     _CG180_NG196_RULES),
    "NG28_DM":     NICEGuideline("NG28",     "Type 2 diabetes in adults",                   _NG28_DIABETES_RULES),
    "CG113":       NICEGuideline("CG113",    "Generalised anxiety disorder",                _CG113_RULES),
    "NG180":       NICEGuideline("NG180",    "Chronic pain",                                _NG180_RULES),
    "CG184":       NICEGuideline("CG184",    "GORD and dyspepsia",                          _CG184_RULES),
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
    Bidirectional class-OR-name matching against all NICE rules.
    Returns all matching CombinationRule objects (may be empty).
    """
    ids_a = {class_a.upper(), name_a.lower()}
    ids_b = {class_b.upper(), name_b.lower()}
    matches: list[CombinationRule] = []

    for rule in _all_rules():
        rule_a_ids = {rule.drug_a.upper(), rule.drug_a.lower()}
        rule_b_ids = {rule.drug_b.upper(), rule.drug_b.lower()}

        forward  = bool(ids_a & rule_a_ids) and bool(ids_b & rule_b_ids)
        backward = bool(ids_a & rule_b_ids) and bool(ids_b & rule_a_ids)

        if not (forward or backward):
            continue

        # Indication match or same-class self-rules (e.g. SSRI+SSRI)
        if rule.indication in shared_indications or rule.indication == "":
            matches.append(rule)
        elif rule.drug_a == rule.drug_b and rule.drug_a.upper() in {class_a.upper(), class_b.upper()}:
            matches.append(rule)

    return matches
