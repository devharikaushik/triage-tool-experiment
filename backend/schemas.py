from typing import List, Optional

from pydantic import BaseModel, Field


class PatientInput(BaseModel):
    age: int = Field(..., ge=0)
    sex: str
    chief_complaint: str
    symptom_duration: str
    symptoms: str
    temperature: str
    pulse: str
    blood_pressure: str
    respiratory_rate: str
    oxygen_saturation: str
    lab_values: str
    comorbidities: Optional[str] = ""


class MedicationInput(BaseModel):
    drug_name: str
    in_stock: bool = False


class ResourceProfileInput(BaseModel):
    centre_name: str

    oxygen: bool = False
    suction: bool = False
    iv_fluids: bool = False
    nebulizer: bool = False
    power_backup: bool = False

    blood_glucose: bool = False
    hemoglobin: bool = False
    urine_test: bool = False
    malaria_test: bool = False
    ecg: bool = False
    xray: bool = False
    ultrasound: bool = False

    start_iv: bool = False
    give_im: bool = False
    manage_airway: bool = False
    intubate: bool = False
    manage_shock: bool = False
    monitor_vitals: bool = False

    medications: List[MedicationInput] = []
