import re
from typing import Any, Dict, List, Optional, Tuple


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"-?\d+(\.\d+)?", str(value))
    return float(match.group()) if match else None


def _parse_bp(bp: Any) -> Tuple[Optional[int], Optional[int]]:
    if bp is None:
        return None, None
    match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", str(bp))
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def _normalize_text(patient_data: Dict[str, Any]) -> str:
    pieces = [
        str(patient_data.get("chief_complaint", "")),
        str(patient_data.get("symptoms", "")),
        str(patient_data.get("lab_values", "")),
        str(patient_data.get("comorbidities", "")),
    ]
    return " ".join(pieces).lower()


def _derive_case_features(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    text = _normalize_text(patient_data)
    temp = _to_float(patient_data.get("temperature"))
    pulse = _to_float(patient_data.get("pulse"))
    rr = _to_float(patient_data.get("respiratory_rate"))
    spo2 = _to_float(patient_data.get("oxygen_saturation"))
    sbp, _ = _parse_bp(patient_data.get("blood_pressure"))

    fever = temp is not None and temp >= 38
    hypotension = sbp is not None and sbp < 90
    tachycardia = pulse is not None and pulse >= 110
    tachypnea = rr is not None and rr >= 24
    hypoxia = spo2 is not None and spo2 < 92

    respiratory_symptoms = any(word in text for word in ["cough", "breath", "wheeze", "chest"])
    gi_symptoms = any(word in text for word in ["vomit", "diarrhea", "abdominal", "abdomen"])
    neuro_symptoms = any(word in text for word in ["seizure", "confus", "weakness", "stroke", "headache"])
    urinary_symptoms = any(word in text for word in ["dysuria", "urine", "flank"])

    if respiratory_symptoms:
        syndrome = "Acute respiratory syndrome"
    elif gi_symptoms:
        syndrome = "Acute gastrointestinal syndrome"
    elif neuro_symptoms:
        syndrome = "Acute neurologic syndrome"
    elif fever:
        syndrome = "Acute febrile illness syndrome"
    else:
        syndrome = "Undifferentiated acute illness syndrome"

    red_flags: List[str] = []
    if hypotension:
        red_flags.append("Hypotension/shock physiology")
    if hypoxia:
        red_flags.append("Hypoxia")
    if tachypnea:
        red_flags.append("Tachypnea/possible respiratory distress")
    if tachycardia:
        red_flags.append("Marked tachycardia")
    if fever and hypotension:
        red_flags.append("Possible sepsis pattern (fever + hypotension)")

    if not red_flags:
        red_flags = ["No immediate physiologic red flags from provided vitals"]

    differentials: List[Dict[str, str]] = []
    if respiratory_symptoms:
        differentials.append(
            {
                "diagnosis": "Lower respiratory tract infection (e.g., pneumonia)",
                "reasoning": "Respiratory symptom cluster with available vital-sign context supports pulmonary infection.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Acute exacerbation of obstructive airway disease",
                "reasoning": "Breathlessness/wheeze pattern can represent airway inflammation or bronchospasm.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Pulmonary vascular/cardiac cause",
                "reasoning": "Dyspnea and chest symptoms require exclusion of cardiopulmonary emergencies.",
            }
        )
    elif gi_symptoms:
        differentials.append(
            {
                "diagnosis": "Acute infectious gastroenteritis",
                "reasoning": "GI-predominant symptoms with acute duration suggest infectious cause.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Intra-abdominal inflammatory process",
                "reasoning": "Persistent abdominal symptoms can indicate surgical or inflammatory pathology.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Volume depletion/electrolyte disturbance",
                "reasoning": "Fluid losses and poor intake can produce systemic instability.",
            }
        )
    elif neuro_symptoms:
        differentials.append(
            {
                "diagnosis": "Acute cerebrovascular event",
                "reasoning": "Focal neurologic complaints require urgent vascular evaluation.",
            }
        )
        differentials.append(
            {
                "diagnosis": "CNS infection/inflammation",
                "reasoning": "Neurologic symptoms with systemic illness can indicate CNS pathology.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Metabolic/toxic encephalopathy",
                "reasoning": "Altered cognition or neurologic change may be secondary to systemic derangement.",
            }
        )
    else:
        differentials.append(
            {
                "diagnosis": "Infection-related acute illness",
                "reasoning": "Common cause of undifferentiated acute presentations.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Cardiopulmonary process",
                "reasoning": "Vital-sign abnormalities can represent primary heart/lung pathology.",
            }
        )
        differentials.append(
            {
                "diagnosis": "Metabolic or dehydration-related illness",
                "reasoning": "Systemic symptoms can stem from fluid, glucose, or electrolyte imbalance.",
            }
        )

    supporting = [
        str(patient_data.get("chief_complaint", "")),
        str(patient_data.get("symptoms", ""))[:180] or "Symptom cluster provided",
    ]
    if fever:
        supporting.append("Documented fever")
    if hypoxia:
        supporting.append("Low oxygen saturation")
    if tachycardia:
        supporting.append("Tachycardia")

    contradictory = []
    if not fever and "infection" in differentials[0]["diagnosis"].lower():
        contradictory.append("No fever documented")
    if not hypoxia and respiratory_symptoms:
        contradictory.append("No hypoxia despite respiratory complaints")
    if not contradictory:
        contradictory = ["No strong contradictory features in provided dataset"]

    rule_outs = ["Shock", "Severe hypoxia", "Acute coronary equivalent"]
    if neuro_symptoms:
        rule_outs.insert(0, "Acute stroke/intracranial event")
    if gi_symptoms and hypotension:
        rule_outs.insert(0, "Severe dehydration with circulatory compromise")

    next_tests = ["Point-of-care glucose", "CBC and basic metabolic panel"]
    if respiratory_symptoms:
        next_tests.append("Chest imaging and pulse oximetry trend")
    if neuro_symptoms:
        next_tests.append("Urgent neuro exam and neuroimaging if deficits present")
    if urinary_symptoms:
        next_tests.append("Urinalysis and renal function")

    if hypotension or hypoxia:
        disposition = "Admit"
    elif fever or tachycardia or tachypnea:
        disposition = "Observe"
    else:
        disposition = "Discharge"

    return {
        "syndrome": syndrome,
        "differentials": differentials[:3],
        "red_flags": red_flags,
        "supporting": supporting,
        "contradictory": contradictory,
        "rule_outs": rule_outs,
        "next_tests": next_tests,
        "disposition": disposition,
    }


def _build_problem_representation(patient_data: Dict[str, Any], features: Dict[str, Any]) -> str:
    age = patient_data.get("age", "Unknown age")
    sex = patient_data.get("sex", "patient")
    complaint = patient_data.get("chief_complaint", "undifferentiated complaint")
    duration = patient_data.get("symptom_duration", "unknown duration")

    temp = _to_float(patient_data.get("temperature"))
    pulse = _to_float(patient_data.get("pulse"))
    rr = _to_float(patient_data.get("respiratory_rate"))
    spo2 = _to_float(patient_data.get("oxygen_saturation"))
    sbp, dbp = _parse_bp(patient_data.get("blood_pressure"))

    vitals = []
    if temp is not None and temp >= 38:
        vitals.append(f"fever {temp:g}C")
    if sbp is not None and sbp < 90:
        vitals.append(f"hypotension {sbp}/{dbp if dbp is not None else '?'}")
    if pulse is not None and pulse >= 110:
        vitals.append(f"tachycardia {pulse:g}/min")
    if rr is not None and rr >= 24:
        vitals.append(f"tachypnea {rr:g}/min")
    if spo2 is not None and spo2 < 92:
        vitals.append(f"hypoxia SpO2 {spo2:g}%")

    comorb = str(patient_data.get("comorbidities", "")).strip()
    comorb_part = f"; comorbidities: {comorb}" if comorb else ""
    vitals_part = f"; notable vitals: {', '.join(vitals)}" if vitals else ""

    return (
        f"{age} year old {sex} with {complaint}, symptom duration {duration}, "
        f"dominant syndrome: {features['syndrome'].lower()}{vitals_part}{comorb_part}"
    )


def generate_clinical_analysis(patient_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """Mock LLM interface. Replace internals with a real API later."""
    complaint = patient_data.get("chief_complaint", "Undifferentiated presentation")
    features = _derive_case_features(patient_data)

    if mode == "student":
        return {
            "Problem Representation": _build_problem_representation(patient_data, features),
            "Dominant Syndrome": features["syndrome"],
            "Top 3 Differentials": features["differentials"],
            "Red Flags": features["red_flags"],
            "Broad Management Principles": [
                "Stabilize airway, breathing, circulation first.",
                "Prioritize urgent life-threatening causes.",
                "Use focused labs/imaging based on the leading syndrome.",
            ],
            "Critical Missing Information": [
                "Mental status and urine output",
                "Medication and allergy history",
                "Focused exam findings",
            ],
        }

    if mode == "clinician":
        return {
            "Ranked Probable Diagnoses": [item["diagnosis"] for item in features["differentials"]],
            "Supporting Findings": features["supporting"],
            "Contradictory Findings": features["contradictory"],
            "Immediate Rule-Outs": features["rule_outs"],
            "Focused Next Tests": features["next_tests"],
            "Suggested Disposition": features["disposition"],
        }

    return {
        "summary": "Peripheral mode clinical assessment generated.",
        "possible_conditions": [
            "Acute systemic illness",
            "Possible shock state if hypotension present",
            "Possible respiratory compromise if hypoxia present",
        ],
    }
