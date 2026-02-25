from pathlib import Path
from typing import Dict, List

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Centre, Competencies, Diagnostics, Infrastructure, Medication
from .reasoning_engine import generate_clinical_analysis
from .triage_engine import run_resource_aware_triage

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Med-Dev-Vi")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "frontend"))

DISCLAIMER = "This tool provides decision support only and does not replace clinical judgment."


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "pages/index.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
        },
    )


@app.get("/student")
def student_page(request: Request):
    return templates.TemplateResponse(
        "pages/student.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "output": None,
        },
    )


@app.post("/student")
def student_submit(
    request: Request,
    db: Session = Depends(get_db),
    age: int = Form(...),
    sex: str = Form(...),
    chief_complaint: str = Form(...),
    symptom_duration: str = Form(...),
    symptoms: str = Form(...),
    temperature: str = Form(...),
    pulse: str = Form(...),
    blood_pressure: str = Form(...),
    respiratory_rate: str = Form(...),
    oxygen_saturation: str = Form(...),
    lab_values: str = Form(...),
    comorbidities: str = Form(""),
):
    _ = db
    patient_data = _build_patient_dict(
        age,
        sex,
        chief_complaint,
        symptom_duration,
        symptoms,
        temperature,
        pulse,
        blood_pressure,
        respiratory_rate,
        oxygen_saturation,
        lab_values,
        comorbidities,
    )
    output = generate_clinical_analysis(patient_data, mode="student")
    return templates.TemplateResponse(
        "pages/student.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "output": output,
            "patient": patient_data,
        },
    )


@app.get("/clinician")
def clinician_page(request: Request):
    return templates.TemplateResponse(
        "pages/clinician.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "output": None,
        },
    )


@app.post("/clinician")
def clinician_submit(
    request: Request,
    db: Session = Depends(get_db),
    age: int = Form(...),
    sex: str = Form(...),
    chief_complaint: str = Form(...),
    symptom_duration: str = Form(...),
    symptoms: str = Form(...),
    temperature: str = Form(...),
    pulse: str = Form(...),
    blood_pressure: str = Form(...),
    respiratory_rate: str = Form(...),
    oxygen_saturation: str = Form(...),
    lab_values: str = Form(...),
    comorbidities: str = Form(""),
):
    _ = db
    patient_data = _build_patient_dict(
        age,
        sex,
        chief_complaint,
        symptom_duration,
        symptoms,
        temperature,
        pulse,
        blood_pressure,
        respiratory_rate,
        oxygen_saturation,
        lab_values,
        comorbidities,
    )
    output = generate_clinical_analysis(patient_data, mode="clinician")
    return templates.TemplateResponse(
        "pages/clinician.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "output": output,
            "patient": patient_data,
        },
    )


@app.get("/peripheral")
def peripheral_page(request: Request, db: Session = Depends(get_db)):
    centre = db.query(Centre).first()
    if not _profile_exists(centre):
        return RedirectResponse(url="/peripheral/setup", status_code=303)

    return templates.TemplateResponse(
        "pages/peripheral.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "output": None,
            "centre": centre,
        },
    )


@app.post("/peripheral")
def peripheral_submit(
    request: Request,
    db: Session = Depends(get_db),
    age: int = Form(...),
    sex: str = Form(...),
    chief_complaint: str = Form(...),
    symptom_duration: str = Form(...),
    symptoms: str = Form(...),
    temperature: str = Form(...),
    pulse: str = Form(...),
    blood_pressure: str = Form(...),
    respiratory_rate: str = Form(...),
    oxygen_saturation: str = Form(...),
    lab_values: str = Form(...),
    comorbidities: str = Form(""),
):
    centre = db.query(Centre).first()
    if not _profile_exists(centre):
        return RedirectResponse(url="/peripheral/setup", status_code=303)

    patient_data = _build_patient_dict(
        age,
        sex,
        chief_complaint,
        symptom_duration,
        symptoms,
        temperature,
        pulse,
        blood_pressure,
        respiratory_rate,
        oxygen_saturation,
        lab_values,
        comorbidities,
    )

    _ = generate_clinical_analysis(patient_data, mode="peripheral")
    output = run_resource_aware_triage(patient_data, centre)

    return templates.TemplateResponse(
        "pages/peripheral.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "output": output,
            "centre": centre,
            "patient": patient_data,
        },
    )


@app.get("/peripheral/setup")
def peripheral_setup_page(request: Request, db: Session = Depends(get_db)):
    centre = db.query(Centre).first()
    existing = _profile_exists(centre)
    return templates.TemplateResponse(
        "pages/peripheral_setup.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "centre": centre,
            "existing": existing,
        },
    )


@app.post("/peripheral/setup")
def peripheral_setup_submit(
    request: Request,
    db: Session = Depends(get_db),
    centre_name: str = Form(...),
    oxygen: bool = Form(False),
    suction: bool = Form(False),
    iv_fluids: bool = Form(False),
    nebulizer: bool = Form(False),
    power_backup: bool = Form(False),
    blood_glucose: bool = Form(False),
    hemoglobin: bool = Form(False),
    urine_test: bool = Form(False),
    malaria_test: bool = Form(False),
    ecg: bool = Form(False),
    xray: bool = Form(False),
    ultrasound: bool = Form(False),
    start_iv: bool = Form(False),
    give_im: bool = Form(False),
    manage_airway: bool = Form(False),
    intubate: bool = Form(False),
    manage_shock: bool = Form(False),
    monitor_vitals: bool = Form(False),
    medication_names: List[str] = Form([]),
    medication_stock: List[str] = Form([]),
):
    centre = db.query(Centre).first()
    if not centre:
        centre = Centre(name=centre_name)
        db.add(centre)
        db.flush()

    centre.name = centre_name

    if not centre.infrastructure:
        centre.infrastructure = Infrastructure(centre_id=centre.id)
    centre.infrastructure.oxygen = oxygen
    centre.infrastructure.suction = suction
    centre.infrastructure.iv_fluids = iv_fluids
    centre.infrastructure.nebulizer = nebulizer
    centre.infrastructure.power_backup = power_backup

    if not centre.diagnostics:
        centre.diagnostics = Diagnostics(centre_id=centre.id)
    centre.diagnostics.blood_glucose = blood_glucose
    centre.diagnostics.hemoglobin = hemoglobin
    centre.diagnostics.urine_test = urine_test
    centre.diagnostics.malaria_test = malaria_test
    centre.diagnostics.ecg = ecg
    centre.diagnostics.xray = xray
    centre.diagnostics.ultrasound = ultrasound

    if not centre.competencies:
        centre.competencies = Competencies(centre_id=centre.id)
    centre.competencies.start_iv = start_iv
    centre.competencies.give_im = give_im
    centre.competencies.manage_airway = manage_airway
    centre.competencies.intubate = intubate
    centre.competencies.manage_shock = manage_shock
    centre.competencies.monitor_vitals = monitor_vitals

    for med in list(centre.medications):
        db.delete(med)

    meds = _parse_medications(medication_names, medication_stock)
    for med in meds:
        centre.medications.append(Medication(drug_name=med["drug_name"], in_stock=med["in_stock"]))

    db.add(centre)
    db.commit()

    return RedirectResponse(url="/peripheral", status_code=303)


@app.get("/peripheral/update")
def peripheral_update_page(request: Request, db: Session = Depends(get_db)):
    centre = db.query(Centre).first()
    if not centre:
        return RedirectResponse(url="/peripheral/setup", status_code=303)

    return templates.TemplateResponse(
        "pages/peripheral_setup.html",
        {
            "request": request,
            "disclaimer": DISCLAIMER,
            "centre": centre,
            "existing": True,
        },
    )


def _build_patient_dict(
    age: int,
    sex: str,
    chief_complaint: str,
    symptom_duration: str,
    symptoms: str,
    temperature: str,
    pulse: str,
    blood_pressure: str,
    respiratory_rate: str,
    oxygen_saturation: str,
    lab_values: str,
    comorbidities: str,
) -> Dict[str, str]:
    return {
        "age": age,
        "sex": sex,
        "chief_complaint": chief_complaint,
        "symptom_duration": symptom_duration,
        "symptoms": symptoms,
        "temperature": temperature,
        "pulse": pulse,
        "blood_pressure": blood_pressure,
        "respiratory_rate": respiratory_rate,
        "oxygen_saturation": oxygen_saturation,
        "lab_values": lab_values,
        "comorbidities": comorbidities,
    }


def _profile_exists(centre: Centre | None) -> bool:
    if not centre:
        return False
    return bool(centre.infrastructure and centre.diagnostics and centre.competencies)


def _parse_medications(names: List[str], stocks: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    stock_map = {item.lower().strip() for item in stocks}

    for name in names:
        clean = name.strip()
        if not clean:
            continue
        out.append({"drug_name": clean, "in_stock": clean.lower() in stock_map})

    return out
