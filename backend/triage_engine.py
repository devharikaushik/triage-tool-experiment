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


def _infer_required_resources(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    required: Set[str] = set()
    stabilization: List[str] = []
    flags: List[str] = []

    systolic = _parse_bp(str(patient_data.get("blood_pressure", "")))
    oxygen_sat = _to_float(patient_data.get("oxygen_saturation"))
    temp = _to_float(patient_data.get("temperature"))
    pulse = _to_float(patient_data.get("pulse"))

    risk = "Low"

    if systolic is not None and systolic < 90:
        flags.append("Shock physiology (SBP < 90)")
        required.update({"iv_fluids", "start_iv", "manage_shock", "monitor_vitals"})
        stabilization.append("Establish IV access and start fluid resuscitation")
        risk = "High"

    if oxygen_sat is not None and oxygen_sat < 90:
        flags.append("Severe hypoxia (SpO2 < 90)")
        required.update({"oxygen", "manage_airway", "monitor_vitals"})
        stabilization.append("Administer supplemental oxygen and monitor saturation")
        risk = "High"

    if temp is not None and temp >= 39 and systolic is not None and systolic < 90:
        flags.append("Possible sepsis pattern (high fever + hypotension)")
        required.update({"iv_fluids", "start_iv", "manage_shock", "blood_glucose"})
        stabilization.append("Begin sepsis stabilization bundle per local protocol")
        risk = "High"

    if pulse is not None and pulse >= 130 and risk != "High":
        flags.append("Marked tachycardia")
        required.update({"monitor_vitals", "blood_glucose"})
        stabilization.append("Continuous monitoring and focused reassessment")
        risk = "Moderate"

    if not flags:
        stabilization.append("Continue routine monitoring and symptomatic care")

    return {
        "risk_level": risk,
        "flags": flags,
        "required_resources": sorted(required),
        "stabilization_steps": stabilization,
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

    refer_immediately = "Yes" if assessment["risk_level"] == "High" and missing else "No"

    pre_referral = assessment["stabilization_steps"]
    if missing:
        pre_referral = pre_referral + [
            "Arrange early referral while continuing achievable stabilization",
            "Send transfer note with vitals and treatments already given",
        ]

    return {
        "Clinical Risk Level": assessment["risk_level"],
        "Stabilization Possible Here": stability,
        "Missing Required Resources": missing,
        "Refer Immediately": refer_immediately,
        "Steps Before Referral": pre_referral,
        "Derived Flags": assessment["flags"],
    }
