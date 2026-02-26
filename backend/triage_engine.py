import re
from typing import Any, Dict, List, Optional, Set

from .models import Centre


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"-?\d+(\.\d+)?", str(value))
    return float(match.group()) if match else None


def _parse_bp(bp: str) -> Optional[int]:
    if not bp:
        return None
    match = re.match(r"\s*(\d{2,3})\s*/\s*(\d{2,3})\s*", str(bp))
    if not match:
        return None
    return int(match.group(1))


def _case_text(patient_data: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(patient_data.get("chief_complaint", "")),
            str(patient_data.get("symptoms", "")),
            str(patient_data.get("lab_values", "")),
            str(patient_data.get("comorbidities", "")),
        ]
    ).lower()


def _rank_top_differentials(patient_data: Dict[str, Any], assessment: Dict[str, Any]) -> List[Dict[str, str]]:
    text = _case_text(patient_data)
    temp = _to_float(patient_data.get("temperature"))
    pulse = _to_float(patient_data.get("pulse"))
    spo2 = _to_float(patient_data.get("oxygen_saturation"))
    systolic = _parse_bp(str(patient_data.get("blood_pressure", "")))

    fever = temp is not None and temp >= 38.0
    hypotension = systolic is not None and systolic < 90
    hypoxia = spo2 is not None and spo2 < 92
    tachy = pulse is not None and pulse >= 110

    candidates: List[Dict[str, Any]] = [
        {"diagnosis": "Community-acquired pneumonia / lower respiratory tract infection", "score": 0, "reason": ""},
        {"diagnosis": "Acute asthma/COPD exacerbation", "score": 0, "reason": ""},
        {"diagnosis": "Sepsis with hemodynamic compromise", "score": 0, "reason": ""},
        {"diagnosis": "Acute coronary syndrome / cardiac ischemia", "score": 0, "reason": ""},
        {"diagnosis": "Pulmonary edema / heart failure exacerbation", "score": 0, "reason": ""},
        {"diagnosis": "Acute gastroenteritis with dehydration", "score": 0, "reason": ""},
        {"diagnosis": "Hypoglycemia or glucose-related metabolic emergency", "score": 0, "reason": ""},
        {"diagnosis": "Acute neurologic emergency (stroke/seizure/CNS event)", "score": 0, "reason": ""},
        {"diagnosis": "Malaria or other febrile parasitic illness", "score": 0, "reason": ""},
        {"diagnosis": "Urinary sepsis / pyelonephritis", "score": 0, "reason": ""},
    ]

    def bump(name: str, points: int, reason: str) -> None:
        for item in candidates:
            if item["diagnosis"] == name:
                item["score"] += points
                if not item["reason"]:
                    item["reason"] = reason
                return

    respiratory = any(word in text for word in ["cough", "dyspnea", "breath", "sputum", "wheeze"])
    chest_pain = "chest pain" in text or "pressure chest" in text or "tightness" in text
    gi = any(word in text for word in ["vomit", "diarrhea", "diarrhoea", "abdominal"])
    neuro = any(word in text for word in ["confus", "seizure", "unconscious", "stroke", "weakness"])
    urinary = any(word in text for word in ["dysuria", "urine", "flank"])
    malaria_pattern = any(word in text for word in ["rigor", "chills", "malaria"])
    edema = any(word in text for word in ["orthopnea", "pnd", "edema", "swelling legs"])

    if respiratory:
        bump("Community-acquired pneumonia / lower respiratory tract infection", 3, "Respiratory symptom cluster is present.")
        bump("Acute asthma/COPD exacerbation", 2, "Breathlessness/wheeze pattern suggests obstructive airway disease.")
    if fever:
        bump("Community-acquired pneumonia / lower respiratory tract infection", 2, "Fever increases likelihood of infection.")
        bump("Sepsis with hemodynamic compromise", 2, "Fever with systemic illness supports sepsis consideration.")
        bump("Malaria or other febrile parasitic illness", 1, "Fever compatible with tropical febrile illness.")
    if hypoxia:
        bump("Community-acquired pneumonia / lower respiratory tract infection", 2, "Low oxygen saturation supports pulmonary process.")
        bump("Pulmonary edema / heart failure exacerbation", 2, "Hypoxia may indicate cardiopulmonary fluid overload.")
    if hypotension:
        bump("Sepsis with hemodynamic compromise", 4, "Hypotension indicates potential circulatory failure.")
        bump("Acute gastroenteritis with dehydration", 2, "Hypotension can result from severe volume depletion.")
    if tachy:
        bump("Sepsis with hemodynamic compromise", 1, "Tachycardia supports systemic stress response.")
        bump("Acute gastroenteritis with dehydration", 1, "Tachycardia can indicate dehydration.")
    if chest_pain:
        bump("Acute coronary syndrome / cardiac ischemia", 4, "Chest pain/tightness requires cardiac rule-out.")
        bump("Pulmonary edema / heart failure exacerbation", 2, "Cardiorespiratory symptoms overlap with heart failure states.")
    if edema:
        bump("Pulmonary edema / heart failure exacerbation", 3, "Fluid overload symptoms support heart failure.")
    if gi:
        bump("Acute gastroenteritis with dehydration", 4, "GI losses strongly suggest gastroenteritis/dehydration.")
    if neuro:
        bump("Acute neurologic emergency (stroke/seizure/CNS event)", 5, "Neurologic danger terms are present.")
    if urinary and fever:
        bump("Urinary sepsis / pyelonephritis", 4, "Urinary symptoms with fever suggest urinary source infection.")
    if "glucose" in text or "sugar" in text:
        bump("Hypoglycemia or glucose-related metabolic emergency", 3, "Glucose-related concern appears in case data.")
    if malaria_pattern and fever:
        bump("Malaria or other febrile parasitic illness", 4, "Fever with rigors/chills raises malaria risk where relevant.")

    if assessment["risk_level"] == "High":
        bump("Sepsis with hemodynamic compromise", 1, "High-risk physiology increases concern for systemic critical illness.")

    ranked = [item for item in candidates if item["score"] > 0]
    if not ranked:
        ranked = [
            {
                "diagnosis": "Undifferentiated acute illness (needs serial reassessment)",
                "score": 1,
                "reason": "Limited discriminating features in submitted data.",
            }
        ]

    ranked.sort(key=lambda x: x["score"], reverse=True)
    top = ranked[:5]
    return [
        {
            "diagnosis": item["diagnosis"],
            "reasoning": item["reason"] or "Supported by available symptom-vital pattern.",
        }
        for item in top
    ]


def _broad_management_paths(
    assessment: Dict[str, Any],
    missing: List[str],
    stability: str,
    refer_immediately: str,
) -> Dict[str, List[str]]:
    manage_here: List[str] = [
        "Reassess ABC (airway, breathing, circulation) and repeat vitals at defined intervals.",
        "Treat the leading syndrome while monitoring for deterioration.",
        "Document response to each intervention and update disposition if risk changes.",
    ]
    if assessment["risk_level"] in {"Moderate", "High"}:
        manage_here.append("Use high-frequency monitoring and senior escalation thresholds.")

    before_referral: List[str] = list(assessment["stabilization_steps"])
    before_referral.extend(
        [
            "Communicate referral early and confirm receiving facility acceptance.",
            "Send transfer note with vitals trend, interventions, and pending concerns.",
            "Escort with staff capable of airway/circulatory support if unstable.",
        ]
    )
    if missing:
        before_referral.insert(0, f"Missing local requirements: {', '.join(missing)}")

    if stability == "Yes" and refer_immediately == "No":
        before_referral = [
            "Referral not immediately required if patient remains stable after reassessment."
        ]

    return {
        "broad_management_if_admitted_here": manage_here,
        "broad_management_before_referral": before_referral,
    }


def _infer_required_resources(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    required: Set[str] = set()
    stabilization: Set[str] = set()
    flags: List[str] = []
    required_diag: Set[str] = set()

    systolic = _parse_bp(str(patient_data.get("blood_pressure", "")))
    oxygen_sat = _to_float(patient_data.get("oxygen_saturation"))
    temp = _to_float(patient_data.get("temperature"))
    pulse = _to_float(patient_data.get("pulse"))
    resp_rate = _to_float(patient_data.get("respiratory_rate"))
    case_text = _case_text(patient_data)

    respiratory_pattern = any(word in case_text for word in ["cough", "breath", "dyspnea", "wheeze", "chest"])
    gi_pattern = any(word in case_text for word in ["vomit", "diarrhea", "diarrhoea", "abdominal", "dehydration"])
    neuro_pattern = any(word in case_text for word in ["confus", "seizure", "unconscious", "stroke", "weakness"])
    chest_pain_pattern = any(word in case_text for word in ["chest pain", "tightness", "pressure chest"])
    malaria_pattern = any(word in case_text for word in ["chills", "rigors", "malaria"])

    fever = temp is not None and temp >= 38.0
    hypotension = systolic is not None and systolic < 90
    severe_hypoxia = oxygen_sat is not None and oxygen_sat < 90
    moderate_hypoxia = oxygen_sat is not None and oxygen_sat < 92
    marked_tachycardia = pulse is not None and pulse >= 130
    tachycardia = pulse is not None and pulse >= 110
    tachypnea = resp_rate is not None and resp_rate >= 24

    high_risk = False
    risk_points = 0

    if hypotension:
        flags.append("Shock physiology (SBP < 90)")
        required.update({"iv_fluids", "start_iv", "manage_shock", "monitor_vitals"})
        stabilization.add("Establish IV access and start fluid resuscitation")
        high_risk = True

    if severe_hypoxia:
        flags.append("Severe hypoxia (SpO2 < 90)")
        required.update({"oxygen", "manage_airway", "monitor_vitals"})
        stabilization.add("Administer supplemental oxygen and monitor saturation")
        high_risk = True
    elif moderate_hypoxia:
        flags.append("Possible hypoxic respiratory compromise (SpO2 < 92)")
        required.update({"oxygen", "monitor_vitals"})
        stabilization.add("Start oxygen if available and reassess saturation trend")
        risk_points += 2

    if fever and hypotension:
        flags.append("Possible sepsis pattern (high fever + hypotension)")
        required.update({"iv_fluids", "start_iv", "manage_shock", "blood_glucose"})
        required_diag.update({"blood_glucose"})
        stabilization.add("Begin sepsis stabilization bundle per local protocol")
        high_risk = True
    elif fever and (tachycardia or tachypnea):
        flags.append("Possible systemic infection pattern (fever + physiologic stress)")
        required.update({"monitor_vitals"})
        required_diag.update({"blood_glucose"})
        stabilization.add("Reassess perfusion, hydration, and progression every 15-30 minutes")
        risk_points += 2

    if marked_tachycardia:
        flags.append("Marked tachycardia")
        required.update({"monitor_vitals", "blood_glucose"})
        required_diag.update({"blood_glucose"})
        stabilization.add("Continuous monitoring and focused reassessment")
        risk_points += 2
    elif tachycardia:
        flags.append("Tachycardia")
        required.update({"monitor_vitals"})
        stabilization.add("Repeat vitals after initial supportive care")
        risk_points += 1

    if tachypnea:
        flags.append("Tachypnea")
        required.update({"monitor_vitals"})
        stabilization.add("Assess work of breathing and escalation threshold")
        risk_points += 1

    if respiratory_pattern:
        flags.append("Respiratory symptom cluster")
        required.update({"monitor_vitals"})
        required_diag.update({"xray"})
        stabilization.add("Position upright and give bronchodilator if wheeze is present")
        risk_points += 1

    if gi_pattern:
        flags.append("Gastrointestinal fluid-loss pattern")
        required.update({"iv_fluids", "start_iv", "monitor_vitals"})
        required_diag.update({"blood_glucose"})
        stabilization.add("Begin oral/IV rehydration based on severity")
        risk_points += 1

    if neuro_pattern:
        flags.append("Neurologic danger pattern")
        required.update({"manage_airway", "monitor_vitals", "blood_glucose"})
        required_diag.update({"blood_glucose"})
        stabilization.add("Check glucose immediately and protect airway if sensorium is reduced")
        high_risk = True

    if chest_pain_pattern:
        flags.append("Chest pain/cardiac risk pattern")
        required.update({"monitor_vitals", "oxygen"})
        required_diag.update({"ecg"})
        stabilization.add("Obtain ECG urgently and monitor for deterioration")
        risk_points += 2

    if malaria_pattern and fever:
        flags.append("Fever with malaria-compatible pattern")
        required_diag.update({"malaria_test"})
        stabilization.add("Perform malaria testing early where endemic risk exists")
        risk_points += 1

    if not flags:
        stabilization.add("Continue routine monitoring and symptomatic care")

    required.update(required_diag)

    if high_risk:
        risk = "High"
    elif risk_points >= 3:
        risk = "Moderate"
    else:
        risk = "Low"

    return {
        "risk_level": risk,
        "flags": flags,
        "required_resources": sorted(required),
        "stabilization_steps": sorted(stabilization),
        "critical_patterns": {
            "shock_or_hypoxia": hypotension or severe_hypoxia,
            "neurologic_danger": neuro_pattern,
            "chest_pain_risk": chest_pain_pattern,
        },
    }


def _build_available_set(centre: Centre) -> Set[str]:
    available: Set[str] = set()

    if centre.infrastructure:
        for key in ["oxygen", "suction", "iv_fluids", "nebulizer", "power_backup"]:
            if getattr(centre.infrastructure, key, False):
                available.add(key)

    if centre.diagnostics:
        for key in [
            "blood_glucose",
            "hemoglobin",
            "urine_test",
            "malaria_test",
            "ecg",
            "xray",
            "ultrasound",
        ]:
            if getattr(centre.diagnostics, key, False):
                available.add(key)

    if centre.competencies:
        for key in ["start_iv", "give_im", "manage_airway", "intubate", "manage_shock", "monitor_vitals"]:
            if getattr(centre.competencies, key, False):
                available.add(key)

    for med in centre.medications:
        if med.in_stock:
            available.add(f"med:{med.drug_name.strip().lower()}")

    return available


def run_resource_aware_triage(patient_data: Dict[str, Any], centre: Centre) -> Dict[str, Any]:
    assessment = _infer_required_resources(patient_data)
    available_resources = _build_available_set(centre)

    missing = [
        resource
        for resource in assessment["required_resources"]
        if resource not in available_resources
    ]

    if not assessment["required_resources"]:
        stability = "Yes"
    elif not missing:
        stability = "Yes"
    elif len(missing) < len(assessment["required_resources"]):
        stability = "Partial"
    else:
        stability = "No"

    critical = assessment["critical_patterns"]
    refer_immediately = (
        "Yes"
        if assessment["risk_level"] == "High" and (missing or critical["chest_pain_risk"] or critical["neurologic_danger"])
        else "No"
    )

    pre_referral = assessment["stabilization_steps"]
    if missing:
        pre_referral = pre_referral + [
            "Arrange early referral while continuing achievable stabilization",
            "Send transfer note with vitals and treatments already given",
        ]

    treatable_here = stability == "Yes" and refer_immediately == "No"
    flag_color = "Green Flag" if treatable_here else "Red Flag"
    flag_message = (
        "Case can be treated here based on current resource and competency cross-verification."
        if treatable_here
        else "Case exceeds current resource/competency capacity; referral pathway required."
    )

    management_paths = _broad_management_paths(assessment, missing, stability, refer_immediately)
    top_differentials = _rank_top_differentials(patient_data, assessment)

    return {
        "Clinical Risk Level": assessment["risk_level"],
        "Stabilization Possible Here": stability,
        "Required Resources for this Case": assessment["required_resources"],
        "Missing Required Resources": missing,
        "Top 5 Differentials": top_differentials,
        "Treatment Feasibility Flag": flag_color,
        "Flag Explanation": flag_message,
        "Refer Immediately": refer_immediately,
        "Steps Before Referral": pre_referral,
        "Broad Management If Admitted Here": management_paths["broad_management_if_admitted_here"],
        "Broad Management Before Referral": management_paths["broad_management_before_referral"],
        "Derived Flags": assessment["flags"],
    }
