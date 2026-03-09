from typing import Dict, Any


def to_adr_patient_data(patient_data: dict, drug_data: dict) -> Dict[str, Any]:
    """
    Converts our system's patient_data + drug_data schema into the format
    expected by ADRAnalyzer (and RMMGenerator, RiskMitigationAnalyzer).

    Our schema:
        patient_data keys: id, fullName, age, gender, chiefComplaint,
            pregnancy_info, currentDiagnosis, pastMedicalConditions,
            allergies, ongoingMedications
        drug_data keys: name, condition

    ADR analyzer schema:
        patient:      { age, gender, diagnosis, condition }
        prescription: [medicine names]
        MedicalHistory: [{ diagnosisName, status, severity }]
    """

    # ── patient block ─────────────────────────────────────────────────────────
    preg        = patient_data.get("pregnancy_info", {})
    is_pregnant = preg.get("pregnancy_status") == "Ongoing Pregnancy"
    is_lactating = preg.get("lactation") == "Yes"

    current_dx_names = [
        dx.get("name", "")
        for dx in patient_data.get("currentDiagnosis", [])
        if dx.get("name")
    ]
    diagnosis_str = ", ".join(current_dx_names) if current_dx_names else drug_data.get("condition", "")

    patient_block = {
        "age":             patient_data.get("age", 0),
        "gender":          patient_data.get("gender", ""),
        "diagnosis":       diagnosis_str,
        "condition":       drug_data.get("condition", ""),
        "pregnancy_status": preg.get("pregnancy_status", "Not Applicable"),
        "is_pregnant":     is_pregnant,
        "trimester":       preg.get("Trimester"),
        "is_lactating":    is_lactating,
    }

    # ── prescription block ────────────────────────────────────────────────────
    prescription = set()
    prescription.add(drug_data.get("name", ""))

    for med in patient_data.get("ongoingMedications", []):
        if med.get("name"):
            prescription.add(med["name"])

    for dx in patient_data.get("currentDiagnosis", []):
        if dx.get("medicationName"):
            prescription.add(dx["medicationName"])

    for cond in patient_data.get("pastMedicalConditions", []):
        if cond.get("treatmentGiven"):
            prescription.add(cond["treatmentGiven"])

    prescription_list = [m for m in prescription if m]

    # ── MedicalHistory block ──────────────────────────────────────────────────
    medical_history = []

    for dx in patient_data.get("currentDiagnosis", []):
        if dx.get("name"):
            medical_history.append({
                "diagnosisName": dx["name"],
                "status":        "Active",
                "severity":      "",
            })

    for cond in patient_data.get("pastMedicalConditions", []):
        if cond.get("conditionName"):
            medical_history.append({
                "diagnosisName": cond["conditionName"],
                "status":        cond.get("status", "Active"),
                "severity":      "",
            })

    return {
        "patient":        patient_block,
        "prescription":   prescription_list,
        "MedicalHistory": medical_history,
    }
