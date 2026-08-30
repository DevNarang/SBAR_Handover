from datetime import datetime, timedelta, date

from sqlalchemy.orm import Session

from app.models import (
    User,
    Ward,
    UserWardAssignment,
    Patient,
    Admission,
    Role,
    Sex,
    AdmissionStatus,
    Protocol,
    Task,
    Escalation,
    EscalationSeverity,
    EscalationStatus,
    Handover,
    HandoverStatus,
    RiskLevel,
    AiUsageLog,
    WardShiftSignoff,
    AuditLog,
    ShiftAssignment,
    ShiftType,
)
from app.security import hash_password
from app.deps import current_shift

DEMO_PASSWORD = "ChangeMe123!"

SYSTEMS = [
    "respiratory",
    "cardiovascular",
    "neurological",
    "genitourinary",
    "musculoskeletal",
    "integumentary",
]


def exams(**overrides):
    base = {s: {"status": "normal", "notes": ""} for s in SYSTEMS}
    for k, v in overrides.items():
        base[k] = v
    return base


def vitals(temp, sbp, dbp, pr, rr, spo2):
    return {
        "temp": temp,
        "bp_systolic": sbp,
        "bp_diastolic": dbp,
        "pr": pr,
        "rr": rr,
        "spo2": spo2,
        "recorded_at": datetime.utcnow().isoformat(),
    }


# Extra census is keyed by MRN so restarts can add missing patients without duplicates.
CENSUS = [
    {
        "mrn": "UHID-10021",
        "name": "Ramesh Patel",
        "age": 62,
        "sex": Sex.male,
        "ward": "Surgical Ward 1",
        "bed": "S1-04",
        "diagnosis": "Post-op laparoscopic cholecystectomy D1",
        "reason": "Acute cholecystitis — laparoscopic cholecystectomy yesterday",
        "handover": "submitted",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "D1 post lap chole. Pain 4/10, ambulating with support. Drain 40 ml serosanguinous this shift.",
            "immediate_concern": "Watch drain output and abdominal distension.",
            "critical_flag": False,
            "medical_history": [
                {"item": "Type 2 diabetes", "notes": "Metformin held peri-op"},
                {"item": "Hypertension", "notes": "Amlodipine 5 mg OD"},
            ],
            "surgical_history": [{"item": "Laparoscopic cholecystectomy", "notes": "Yesterday, 4 ports"}],
            "medications": [
                {"name": "Paracetamol", "dose": "1g", "route": "IV", "frequency": "Q6H", "notes": ""},
                {"name": "Enoxaparin", "dose": "40mg", "route": "SC", "frequency": "OD", "notes": "VTE"},
                {"name": "Pantoprazole", "dose": "40mg", "route": "IV", "frequency": "OD", "notes": ""},
            ],
            "nkda": True,
            "allergies": [],
            "vitals": None,  # filled below
            "system_exams": exams(integumentary={"status": "abnormal", "notes": "Port sites clean, drain in LUQ"}),
            "significant_findings": "Drain LUQ 40 ml serosanguinous; abdomen soft, mild RUQ tenderness.",
            "diagnostics": [
                {"test": "WBC", "result": "11.2 x10^9/L", "date": str(date.today()), "abnormal": True},
                {"test": "CRP", "result": "48 mg/L", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "IV fluids 80 ml/hr, analgesia, early mobilisation, drain chart.",
            "nursing_care": "Drain Q4H, incentive spirometry, CBG QID, VTE stockings.",
            "team_communication": "Surgical team aware of drain increase vs last shift.",
            "follow_up": "US abdomen if drain >100 ml or fever.",
            "home_care_needs": "Likely not this admission.",
        },
        "vitals": (37.4, 128, 78, 92, 18, 97),
    },
    {
        "mrn": "UHID-10022",
        "name": "Meera Joshi",
        "age": 45,
        "sex": Sex.female,
        "ward": "Surgical Ward 1",
        "bed": "S1-07",
        "diagnosis": "Exploratory laparotomy — small bowel obstruction D2",
        "reason": "SBO, failed conservative management, laparotomy with adhesiolysis",
        "handover": "draft",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "D2 post laparotomy. NGT on free drainage 400 ml bilious. Not yet passing flatus. PCA in situ.",
            "immediate_concern": "Ileus vs early obstruction — NGT output still high.",
            "critical_flag": False,
            "medical_history": [
                {"item": "Hypothyroidism", "notes": "Thyroxine 75 mcg OD, given this morning"},
                {"item": "Iron-deficiency anaemia", "notes": "Hb 9.8 on admission"},
            ],
            "surgical_history": [
                {"item": "LSCS x2", "notes": "2012, 2016"},
                {"item": "Exploratory laparotomy + adhesiolysis", "notes": "This admission D2"},
            ],
            "medications": [
                {"name": "Morphine PCA", "dose": "1mg bolus", "route": "IV", "frequency": "5 min lockout", "notes": "Used 8 mg this shift"},
                {"name": "Thyroxine", "dose": "75mcg", "route": "PO", "frequency": "OD", "notes": "NG if NBM"},
                {"name": "Cefuroxime", "dose": "1.5g", "route": "IV", "frequency": "Q8H", "notes": "Day 2 of 3"},
            ],
            "nkda": False,
            "allergies": [{"allergen": "Penicillin", "reaction": "Rash", "severity": "moderate"}],
            "system_exams": exams(
                respiratory={"status": "abnormal", "notes": "Basal crackles right, incentive spirometry poor"},
                genitourinary={"status": "abnormal", "notes": "IDC 30 ml/hr, concentrated"},
                integumentary={"status": "abnormal", "notes": "Midline dressing dry, NGT taped"},
            ),
            "significant_findings": "Abdomen distended, tympanic, wound dry. Bowel sounds sluggish.",
            "diagnostics": [
                {"test": "K+", "result": "3.2 mmol/L", "date": str(date.today()), "abnormal": True},
                {"test": "AXR", "result": "Dilated small bowel loops", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "NGT free drainage, replace losses, K replacement, NBM, IV fluids.",
            "nursing_care": "NGT chart, I/O hourly, PCA observations, sit out of bed, chest physio.",
            "team_communication": "Surgical registrar to review electrolytes this evening.",
            "follow_up": "Repeat K+ after replacement; consider TPN if NBM continues.",
            "home_care_needs": "",
        },
        "vitals": (37.8, 118, 72, 98, 22, 95),
    },
    {
        "mrn": "UHID-10023",
        "name": "Arjun Desai",
        "age": 28,
        "sex": Sex.male,
        "ward": "Surgical Ward 1",
        "bed": "S1-12",
        "diagnosis": "ORIF right tibia D1",
        "reason": "RTA, closed tibial shaft fracture, ORIF last night",
        "handover": "submitted",
        "risk": RiskLevel.stable,
        "sbar": {
            "current_situation": "D1 post ORIF tibia. Neurovascular intact. Pain 3/10 on tramadol. NWB right leg.",
            "immediate_concern": "Compartment syndrome watch — calf soft, sensation intact.",
            "critical_flag": False,
            "medical_history": [{"item": "Asthma", "notes": "Salbutamol PRN, last attack 2 years ago"}],
            "surgical_history": [{"item": "ORIF right tibia", "notes": "Last night, IM nail"}],
            "medications": [
                {"name": "Tramadol", "dose": "50mg", "route": "PO", "frequency": "Q6H", "notes": ""},
                {"name": "Enoxaparin", "dose": "40mg", "route": "SC", "frequency": "OD", "notes": ""},
                {"name": "Salbutamol", "dose": "2 puffs", "route": "INH", "frequency": "PRN", "notes": ""},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                musculoskeletal={"status": "abnormal", "notes": "Backslab, NWB, pulses present, CRT <2s"},
                integumentary={"status": "abnormal", "notes": "Surgical wound covered, no soak"},
            ),
            "significant_findings": "Right calf soft, equal sensation to left, toes warm and pink.",
            "diagnostics": [{"test": "XR tibia", "result": "Nail in situ, alignment good", "date": str(date.today()), "abnormal": False}],
            "immediate_treatment": "Elevation, ice, analgesia, NWB, DVT prophylaxis.",
            "nursing_care": "NV obs Q2H x 24h, pain score, physio NWB education.",
            "team_communication": "Ortho SHO aware; compartment checklist at bedside.",
            "follow_up": "Ortho OPD 2 weeks with XR.",
            "home_care_needs": "Crutches, NWB advice, wound clinic if discharged tomorrow.",
        },
        "vitals": (36.8, 122, 76, 78, 16, 98),
        "discharge": date.today() + timedelta(days=2),
    },
    {
        "mrn": "UHID-10024",
        "name": "Fatima Begum",
        "age": 71,
        "sex": Sex.female,
        "ward": "Surgical Ward 2",
        "bed": "S2-02",
        "diagnosis": "Left total knee replacement D3",
        "reason": "Severe OA left knee — elective TKR",
        "handover": "accepted",
        "risk": RiskLevel.stable,
        "sbar": {
            "current_situation": "D3 post left TKR. Mobilising with walker 20 m. Hb 9.1. Wound dry.",
            "immediate_concern": "Post-op anaemia — no active bleed.",
            "critical_flag": False,
            "medical_history": [
                {"item": "Osteoarthritis", "notes": "Bilateral knees"},
                {"item": "CKD stage 3", "notes": "Baseline creatinine 1.4"},
                {"item": "Atrial fibrillation", "notes": "Apixaban held peri-op, restart D3 if haemostasis OK"},
            ],
            "surgical_history": [{"item": "Left TKR", "notes": "D3, cemented"}],
            "medications": [
                {"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""},
                {"name": "Apixaban", "dose": "5mg", "route": "PO", "frequency": "BD", "notes": "Restart tonight if OK"},
                {"name": "Ferrous sulfate", "dose": "200mg", "route": "PO", "frequency": "OD", "notes": ""},
            ],
            "nkda": False,
            "allergies": [{"allergen": "NSAIDs", "reaction": "Wheeze", "severity": "high"}],
            "system_exams": exams(
                cardiovascular={"status": "abnormal", "notes": "Irregularly irregular, rate controlled"},
                musculoskeletal={"status": "abnormal", "notes": "Left knee ROM 0–80, drain out"},
                integumentary={"status": "abnormal", "notes": "Wound dry, mild bruising"},
            ),
            "significant_findings": "No calf swelling. Drain removed. Hb drop 11.4 → 9.1 expected.",
            "diagnostics": [{"test": "Hb", "result": "9.1 g/dL", "date": str(date.today()), "abnormal": True}],
            "immediate_treatment": "Restart apixaban tonight if wound dry; iron; physio BD.",
            "nursing_care": "Falls risk, walker, wound check, AF rate, I/O.",
            "team_communication": "Ortho and cardiology agreed restart anticoagulation.",
            "follow_up": "TKR clinic 6 weeks; GP for Hb check 1 week.",
            "home_care_needs": "Home physio, raised toilet seat, family support.",
        },
        "vitals": (36.6, 134, 82, 88, 16, 97),
        "discharge": date.today() + timedelta(days=3),
    },
    {
        "mrn": "UHID-10025",
        "name": "Sanjay Kulkarni",
        "age": 54,
        "sex": Sex.male,
        "ward": "Medical Ward A",
        "bed": "MA-03",
        "diagnosis": "Community-acquired pneumonia",
        "reason": "Fever, hypoxia, productive cough 4 days",
        "handover": "submitted",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "CAP day 3 IV antibiotics. SpO2 93% on 2 L NC. Cough productive yellow. CURB-65 = 2.",
            "immediate_concern": "Wean oxygen carefully; still hypoxic on air (88% trial).",
            "critical_flag": False,
            "medical_history": [
                {"item": "COPD", "notes": "FEV1 55%, on inhalers"},
                {"item": "Ex-smoker", "notes": "40 pack years, quit 2019"},
            ],
            "surgical_history": [],
            "medications": [
                {"name": "Ceftriaxone", "dose": "2g", "route": "IV", "frequency": "OD", "notes": "Day 3"},
                {"name": "Azithromycin", "dose": "500mg", "route": "PO", "frequency": "OD", "notes": "Day 3 of 5"},
                {"name": "Salbutamol / Ipratropium", "dose": "neb", "route": "NEB", "frequency": "Q6H", "notes": ""},
                {"name": "Oxygen", "dose": "2L", "route": "NC", "frequency": "continuous", "notes": "Target SpO2 88–92%"},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                respiratory={"status": "abnormal", "notes": "Right basal crackles, reduced AE, productive cough"},
                cardiovascular={"status": "normal", "notes": "HS dual, no oedema"},
            ),
            "significant_findings": "Work of breathing mild. Sputum culture pending. CXR right lower lobe consolidation.",
            "diagnostics": [
                {"test": "CXR", "result": "RLL consolidation", "date": str(date.today()), "abnormal": True},
                {"test": "WBC", "result": "14.6", "date": str(date.today()), "abnormal": True},
                {"test": "ABG", "result": "pH 7.39 pCO2 48 pO2 62 on 2L", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "Continue IV Abx, nebs, O2 target 88–92%, chest physio.",
            "nursing_care": "SpO2 Q2H, sputum chart, sit up for meals, VTE.",
            "team_communication": "Medical team — step down O2 trial in morning.",
            "follow_up": "Repeat CXR in 6 weeks if smoker history.",
            "home_care_needs": "Inhaler technique, smoking relapse prevention.",
        },
        "vitals": (38.1, 142, 88, 104, 24, 93),
    },
    {
        "mrn": "UHID-10026",
        "name": "Lakshmi Rao",
        "age": 38,
        "sex": Sex.female,
        "ward": "Medical Ward A",
        "bed": "MA-08",
        "diagnosis": "DKA, newly diagnosed T1DM",
        "reason": "Polyuria, vomiting, glucose 28 mmol/L, ketones 4.2",
        "handover": "submitted",
        "risk": RiskLevel.critical,
        "sbar": {
            "current_situation": "DKA protocol hour 8. Glucose 14.2, ketones 1.1, K 3.9. FRIII insulin running. Alert, sipping water.",
            "immediate_concern": "Hypokalaemia risk on insulin; do not stop FRIII until ketones <0.6 and eating.",
            "critical_flag": True,
            "medical_history": [{"item": "Newly diagnosed T1DM", "notes": "No prior history"}],
            "surgical_history": [],
            "medications": [
                {"name": "Actrapid FRIII", "dose": "per protocol", "route": "IV", "frequency": "continuous", "notes": "Fixed-rate insulin infusion"},
                {"name": "KCl in 0.9% NaCl", "dose": "40 mmol/L", "route": "IV", "frequency": "continuous", "notes": "Via large-bore cannula"},
                {"name": "Long-acting insulin", "dose": "not started", "route": "SC", "frequency": "—", "notes": "Start when eating"},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                neurological={"status": "normal", "notes": "GCS 15, no headache"},
                genitourinary={"status": "abnormal", "notes": "Polyuria settling, ketones falling"},
            ),
            "significant_findings": "No Kussmaul now. Abdomen soft. Cannula right ACF, second line left hand.",
            "diagnostics": [
                {"test": "VBG", "result": "pH 7.32 HCO3 16", "date": str(date.today()), "abnormal": True},
                {"test": "Ketones", "result": "1.1 mmol/L", "date": str(date.today()), "abnormal": True},
                {"test": "K+", "result": "3.9 mmol/L", "date": str(date.today()), "abnormal": False},
            ],
            "immediate_treatment": "Continue DKA protocol, hourly glucose/ketones/K, medical review if pH <7.3 again.",
            "nursing_care": "Hourly DKA chart, 2 working IV lines, hypoglycaemia kit at bedside, 1:1 until stable.",
            "team_communication": "Medical registrar — diabetes CNS in morning for education.",
            "follow_up": "Diabetes clinic 1 week post discharge.",
            "home_care_needs": "Glucometer, ketone meter, sick-day rules teaching.",
        },
        "vitals": (36.9, 108, 64, 112, 20, 98),
    },
    {
        "mrn": "UHID-10027",
        "name": "Vikram Singh",
        "age": 67,
        "sex": Sex.male,
        "ward": "ICU",
        "bed": "ICU-02",
        "diagnosis": "Septic shock — abdominal source, D2 post repair",
        "reason": "Perforated viscus, hypotension, lactate 4.8 post-op",
        "handover": "submitted",
        "risk": RiskLevel.critical,
        "sbar": {
            "current_situation": "Ventilated SIMV, FiO2 0.45, noradrenaline 0.12 mcg/kg/min. Lactate 2.1 falling. MAP 72.",
            "immediate_concern": "Vasopressor dependent; watch abdominal drain and IAP.",
            "critical_flag": True,
            "medical_history": [
                {"item": "IHD", "notes": "Stent 2019"},
                {"item": "T2DM", "notes": "Insulin sliding scale"},
            ],
            "surgical_history": [{"item": "Laparotomy + perforation repair", "notes": "D2, drain in pelvis"}],
            "medications": [
                {"name": "Noradrenaline", "dose": "0.12 mcg/kg/min", "route": "IV", "frequency": "infusion", "notes": "Central line"},
                {"name": "Meropenem", "dose": "1g", "route": "IV", "frequency": "Q8H", "notes": ""},
                {"name": "Fentanyl", "dose": "50 mcg/hr", "route": "IV", "frequency": "infusion", "notes": "Sedation"},
                {"name": "Insulin sliding scale", "dose": "variable", "route": "IV", "frequency": "hourly", "notes": ""},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                respiratory={"status": "abnormal", "notes": "Intubated ETT 8.0 at 22 cm, equal AE"},
                cardiovascular={"status": "abnormal", "notes": "On NA, cool peripheries improving"},
                neurological={"status": "abnormal", "notes": "RASS -2, pupils equal"},
                genitourinary={"status": "abnormal", "notes": "IDC 0.6 ml/kg/hr"},
                integumentary={"status": "abnormal", "notes": "Laparotomy dressing dry, pelvic drain 80 ml haemoserous"},
            ),
            "significant_findings": "IAP 12 mmHg. No new ST changes. Family updated at 10:00.",
            "diagnostics": [
                {"test": "Lactate", "result": "2.1 mmol/L", "date": str(date.today()), "abnormal": True},
                {"test": "ABG", "result": "pH 7.36 pO2 92 on FiO2 0.45", "date": str(date.today()), "abnormal": False},
            ],
            "immediate_treatment": "Wean NA if MAP >70, continue Abx, lung-protective vent, stress ulcer prophylaxis.",
            "nursing_care": "Hourly neuro/vent/vasoactive chart, drain, IAP Q4H, eye care, pressure care Q2H.",
            "team_communication": "ICU consultant round 16:00; surgery aware of drain.",
            "follow_up": "CT if lactate rises or drain becomes faeculent.",
            "home_care_needs": "N/A — ICU.",
        },
        "vitals": (38.4, 92, 54, 118, 18, 96),
    },
    {
        "mrn": "UHID-10028",
        "name": "Anita Sharma",
        "age": 33,
        "sex": Sex.female,
        "ward": "Surgical Ward 1",
        "bed": "S1-02",
        "diagnosis": "Acute appendicitis — lap appendicectomy D0",
        "reason": "RIF pain 18 hours, fever, raised WBC, laparoscopic appendicectomy this morning",
        "handover": "submitted",
        "risk": RiskLevel.stable,
        "sbar": {
            "current_situation": "D0 post lap appy. Eating sips. Pain 3/10. Passed urine. Wound ports dry.",
            "immediate_concern": "None immediate — watch for ileus or collection.",
            "critical_flag": False,
            "medical_history": [{"item": "None significant", "notes": "G2P1, not pregnant (beta-hCG negative)"}],
            "surgical_history": [{"item": "Lap appendicectomy", "notes": "This morning, mildly inflamed appendix"}],
            "medications": [
                {"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""},
                {"name": "Ibuprofen", "dose": "400mg", "route": "PO", "frequency": "Q8H", "notes": "With food"},
                {"name": "Co-amoxiclav", "dose": "1.2g", "route": "IV", "frequency": "Q8H", "notes": "24h only"},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                integumentary={"status": "abnormal", "notes": "3 ports, no ooze"},
            ),
            "significant_findings": "Abdomen soft, RIF tenderness expected. Bowel sounds present.",
            "diagnostics": [{"test": "WBC", "result": "13.1 pre-op, pending post-op", "date": str(date.today()), "abnormal": True}],
            "immediate_treatment": "Analgesia, early diet, mobilise, 24h Abx.",
            "nursing_care": "Wound check, urine output, antiemetic PRN, discharge if eating this evening.",
            "team_communication": "Day-case pathway if pain controlled.",
            "follow_up": "GP if fever or RIF pain after 48h.",
            "home_care_needs": "Wound care leaflet, no heavy lifting 2 weeks.",
        },
        "vitals": (37.1, 118, 70, 84, 16, 99),
        "discharge": date.today() + timedelta(days=1),
    },
    {
        "mrn": "UHID-10029",
        "name": "Joseph Mathew",
        "age": 58,
        "sex": Sex.male,
        "ward": "Surgical Ward 2",
        "bed": "S2-06",
        "diagnosis": "Diabetic foot ulcer — left hallux, wet gangrene, D1 post I&D",
        "reason": "Fever, left great toe gangrene, incision and drainage + IV Abx",
        "handover": "submitted",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "D1 post I&D left hallux. Dressing soaked seropurulent x1 this shift. BSL 11–14. On IV pip-tazo.",
            "immediate_concern": "Spreading cellulitis vs residual collection — mark cellulitis border.",
            "critical_flag": False,
            "medical_history": [
                {"item": "T2DM", "notes": "20 years, on insulin"},
                {"item": "CKD 3", "notes": "eGFR 48"},
                {"item": "Peripheral neuropathy", "notes": "10g monofilament absent left"},
            ],
            "surgical_history": [{"item": "I&D left hallux", "notes": "Yesterday"}],
            "medications": [
                {"name": "Piperacillin-tazobactam", "dose": "4.5g", "route": "IV", "frequency": "Q8H", "notes": "Renal dose discussed"},
                {"name": "Insulin glargine", "dose": "18U", "route": "SC", "frequency": "nocte", "notes": ""},
                {"name": "Actrapid sliding scale", "dose": "variable", "route": "SC", "frequency": "QID", "notes": ""},
            ],
            "nkda": False,
            "allergies": [{"allergen": "Sulfa", "reaction": "Stevens-Johnson (remote)", "severity": "high"}],
            "system_exams": exams(
                musculoskeletal={"status": "abnormal", "notes": "Left hallux dressing, pulses dopplerable"},
                integumentary={"status": "abnormal", "notes": "Cellulitis to midfoot, border marked 08:00"},
                neurological={"status": "abnormal", "notes": "Glove-and-stocking sensory loss"},
            ),
            "significant_findings": "No crepitus. Temp 37.9. Wound swab sent.",
            "diagnostics": [
                {"test": "CRP", "result": "96", "date": str(date.today()), "abnormal": True},
                {"test": "XR foot", "result": "No osteomyelitis obvious", "date": str(date.today()), "abnormal": False},
            ],
            "immediate_treatment": "IV Abx, daily dressing, BSL 8–12 target, vascular review.",
            "nursing_care": "Offload heel, dressing BD if soak, mark cellulitis, BSL QID.",
            "team_communication": "Vascular and endocrinology both reviewing tomorrow.",
            "follow_up": "MRI if not improving in 48h.",
            "home_care_needs": "Likely district nurse dressings if discharged later.",
        },
        "vitals": (37.9, 148, 86, 96, 18, 96),
    },
    {
        "mrn": "UHID-10030",
        "name": "Priyanka Nair",
        "age": 26,
        "sex": Sex.female,
        "ward": "Medical Ward A",
        "bed": "MA-11",
        "diagnosis": "Acute pyelonephritis",
        "reason": "Fever 39.2, left flank pain, dysuria, vomiting",
        "handover": "draft",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "Pyelonephritis day 1. After 2 L fluids, vomiting settled. Still febrile. IV gentamicin + amox given.",
            "immediate_concern": "Pregnancy test negative. Watch urine output and repeat cultures.",
            "critical_flag": False,
            "medical_history": [{"item": "Recurrent UTI", "notes": "3 episodes last year"}],
            "surgical_history": [],
            "medications": [
                {"name": "Gentamicin", "dose": "5mg/kg", "route": "IV", "frequency": "OD", "notes": "Level before 3rd dose"},
                {"name": "Amoxicillin", "dose": "1g", "route": "IV", "frequency": "Q8H", "notes": ""},
                {"name": "Paracetamol", "dose": "1g", "route": "PO", "frequency": "Q6H", "notes": ""},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                genitourinary={"status": "abnormal", "notes": "Left renal angle tenderness, dysuria"},
            ),
            "significant_findings": "No peritonism. Urine dip +nitrite +leu +blood.",
            "diagnostics": [
                {"test": "Urine culture", "result": "pending", "date": str(date.today()), "abnormal": True},
                {"test": "WBC", "result": "16.4", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "IV Abx, fluids, analgesia, antiemetic.",
            "nursing_care": "Q4H temp, I/O, encourage oral fluids, pregnancy already excluded.",
            "team_communication": "If not settling 48h — US KUB.",
            "follow_up": "GP urine after Abx course.",
            "home_care_needs": "Hydration advice.",
        },
        "vitals": (38.6, 110, 68, 108, 18, 98),
    },
    {
        "mrn": "UHID-10031",
        "name": "Harish Reddy",
        "age": 49,
        "sex": Sex.male,
        "ward": "Medical Ward A",
        "bed": "MA-14",
        "diagnosis": "Acute decompensated heart failure",
        "reason": "Orthopnoea, bilateral oedema, NT-proBNP 4800",
        "handover": "submitted",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "ADHF day 2. After 80 mg IV furosemide, 1.8 L negative. Oedema improving. On 1 L O2.",
            "immediate_concern": "Hypotension if over-diuresed; K 3.4 this morning.",
            "critical_flag": False,
            "medical_history": [
                {"item": "HFrEF 35%", "notes": "Echo 2025"},
                {"item": "Hypertension", "notes": ""},
                {"item": "T2DM", "notes": "Metformin 1g BD"},
            ],
            "surgical_history": [{"item": "CABG", "notes": "2018"}],
            "medications": [
                {"name": "Furosemide", "dose": "80mg", "route": "IV", "frequency": "BD", "notes": "Hold if SBP <90"},
                {"name": "Bisoprolol", "dose": "2.5mg", "route": "PO", "frequency": "OD", "notes": "Held this morning SBP 88"},
                {"name": "Ramipril", "dose": "2.5mg", "route": "PO", "frequency": "OD", "notes": "Held"},
                {"name": "Spironolactone", "dose": "25mg", "route": "PO", "frequency": "OD", "notes": ""},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                respiratory={"status": "abnormal", "notes": "Bilateral basal crackles, improving"},
                cardiovascular={"status": "abnormal", "notes": "Elevated JVP, pitting oedema to knees"},
            ),
            "significant_findings": "Weight 84.2 → 82.4 kg. No chest pain. ECG no new ischaemia.",
            "diagnostics": [
                {"test": "NT-proBNP", "result": "4800", "date": str(date.today()), "abnormal": True},
                {"test": "K+", "result": "3.4", "date": str(date.today()), "abnormal": True},
                {"test": "CXR", "result": "Pulmonary oedema, improving", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "IV diuretic, K replacement, daily weight, fluid restrict 1.5 L.",
            "nursing_care": "Daily weight before breakfast, strict I/O, sit upright, TED stockings off while oedematous.",
            "team_communication": "Cardiology — restart ACE/BB when SBP >100.",
            "follow_up": "HF nurse clinic 1 week.",
            "home_care_needs": "Daily weights at home, salt restriction education.",
        },
        "vitals": (36.7, 96, 62, 92, 22, 94),
    },
    {
        "mrn": "UHID-10032",
        "name": "Sunita Devi",
        "age": 81,
        "sex": Sex.female,
        "ward": "Medical Ward A",
        "bed": "MA-01",
        "diagnosis": "Delirium on UTI, frailty",
        "reason": "Confusion, falls at home, positive urine culture E. coli",
        "handover": "returned",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "Hyperactive delirium improving. CAM positive overnight, now more oriented. On IV ceftriaxone. 1:1 at night.",
            "immediate_concern": "Falls risk — bed rails up, low bed, call bell in reach.",
            "critical_flag": False,
            "medical_history": [
                {"item": "Dementia (mild)", "notes": "Donepezil 5 mg"},
                {"item": "Osteoporosis", "notes": "Previous Colles fracture"},
                {"item": "Hypertension", "notes": ""},
            ],
            "surgical_history": [{"item": "Right hip hemiarthroplasty", "notes": "2019"}],
            "medications": [
                {"name": "Ceftriaxone", "dose": "1g", "route": "IV", "frequency": "OD", "notes": "Day 2"},
                {"name": "Donepezil", "dose": "5mg", "route": "PO", "frequency": "nocte", "notes": ""},
                {"name": "Haloperidol", "dose": "0.5mg", "route": "PO", "frequency": "PRN", "notes": "Avoid if possible"},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                neurological={"status": "abnormal", "notes": "AMTS 6/10, fluctuating attention"},
                genitourinary={"status": "abnormal", "notes": "No IDC, pads, urine cloudy improving"},
                musculoskeletal={"status": "abnormal", "notes": "Unsteady, needs 1 assist"},
            ),
            "significant_findings": "No new focal neurology. CT head no bleed. Daughter is NOK.",
            "diagnostics": [
                {"test": "Urine culture", "result": "E. coli sensitive to ceftriaxone", "date": str(date.today()), "abnormal": True},
                {"test": "CT head", "result": "Age-related atrophy, no bleed", "date": str(date.today()), "abnormal": False},
            ],
            "immediate_treatment": "Abx, reorientation, avoid night sedation, treat constipation.",
            "nursing_care": "Falls bundle, 1:1 overnight, glasses/hearing aid on, food chart.",
            "team_communication": "Need collateral from daughter for baseline — please call 19:00.",
            "follow_up": "Geriatrics review; social work for package of care.",
            "home_care_needs": "Likely increased homecare; not safe for same-day discharge.",
        },
        "vitals": (37.2, 154, 78, 86, 18, 96),
        "review_comment": "Please add AMTS trend and last bowel motion before resubmit.",
    },
    {
        "mrn": "UHID-10033",
        "name": "Omar Farooq",
        "age": 41,
        "sex": Sex.male,
        "ward": "Surgical Ward 2",
        "bed": "S2-09",
        "diagnosis": "Acute pancreatitis (gallstone), BISAP 2",
        "reason": "Epigastric pain radiating to back, lipase 1200, US gallstones",
        "handover": "submitted",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "Pancreatitis day 2. Pain better (6→3). Tolerating oral fluids. CRP 180 (from 90). Not ITU.",
            "immediate_concern": "Rising CRP — watch for necrosis/collection; keep NBM if pain returns.",
            "critical_flag": False,
            "medical_history": [{"item": "Alcohol 8 units/week", "notes": "Not alcohol-related this episode"}],
            "surgical_history": [],
            "medications": [
                {"name": "IV Hartmann's", "dose": "100 ml/hr", "route": "IV", "frequency": "continuous", "notes": ""},
                {"name": "Morphine", "dose": "5mg", "route": "IV", "frequency": "PRN Q4H", "notes": "Used once"},
                {"name": "Ondansetron", "dose": "4mg", "route": "IV", "frequency": "PRN", "notes": ""},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                genitourinary={"status": "normal", "notes": "Urine output 0.8 ml/kg/hr"},
            ),
            "significant_findings": "Abdomen soft, epigastric tenderness. No Grey Turner/Cullen. US: multiple stones, CBD 5 mm.",
            "diagnostics": [
                {"test": "Lipase", "result": "1200 → 640", "date": str(date.today()), "abnormal": True},
                {"test": "CRP", "result": "180", "date": str(date.today()), "abnormal": True},
                {"test": "US abdomen", "result": "Gallstones, no choledocholithiasis seen", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "IV fluids, analgesia, early oral intake as tolerated, VTE.",
            "nursing_care": "Pain score, I/O, glucose, NBM only if vomiting.",
            "team_communication": "Surgical — index cholecystectomy this admission if settles.",
            "follow_up": "MRCP if LFTs rise.",
            "home_care_needs": "Low-fat diet advice after cholecystectomy.",
        },
        "vitals": (37.3, 126, 80, 90, 18, 97),
    },
    {
        "mrn": "UHID-10034",
        "name": "Grace Fernandes",
        "age": 19,
        "sex": Sex.female,
        "ward": "ICU",
        "bed": "ICU-05",
        "diagnosis": "Status asthmaticus, day 1 ICU",
        "reason": "Life-threatening asthma, poor response to nebs, admitted ICU for monitoring",
        "handover": "submitted",
        "risk": RiskLevel.critical,
        "sbar": {
            "current_situation": "Not intubated. On continuous salbutamol neb, MgSO4 given, hydrocortisone. Peak flow 35% predicted, improving. Speaking words.",
            "immediate_concern": "Silent chest / tiring — crash tray and airway plan at bedside.",
            "critical_flag": True,
            "medical_history": [
                {"item": "Severe asthma", "notes": "3 prior ICU admissions"},
                {"item": "Allergic rhinitis", "notes": ""},
            ],
            "surgical_history": [],
            "medications": [
                {"name": "Salbutamol", "dose": "continuous neb", "route": "NEB", "frequency": "continuous", "notes": ""},
                {"name": "Ipratropium", "dose": "500mcg", "route": "NEB", "frequency": "Q4H", "notes": ""},
                {"name": "Hydrocortisone", "dose": "100mg", "route": "IV", "frequency": "Q6H", "notes": ""},
                {"name": "Magnesium sulfate", "dose": "2g", "route": "IV", "frequency": "stat given", "notes": ""},
                {"name": "Oxygen", "dose": "target 94–98%", "route": "FM", "frequency": "continuous", "notes": ""},
            ],
            "nkda": False,
            "allergies": [{"allergen": "Aspirin", "reaction": "Wheeze", "severity": "high"}],
            "system_exams": exams(
                respiratory={"status": "abnormal", "notes": "Widespread wheeze, accessory muscles, equal AE"},
                cardiovascular={"status": "normal", "notes": "Tachycardic from salbutamol"},
            ),
            "significant_findings": "ABG pCO2 38 (was 32) — watch for rising CO2. CXR no pneumothorax.",
            "diagnostics": [
                {"test": "ABG", "result": "pH 7.41 pCO2 38 pO2 78 on 40%", "date": str(date.today()), "abnormal": True},
                {"test": "PEFR", "result": "180 L/min (pred 450)", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "Continuous nebs, steroids, consider aminophylline if tiring, NIPPV only with ICU consultant.",
            "nursing_care": "1:1, PEFR Q1H if able, continuous SpO2, sit forward, calm environment.",
            "team_communication": "ICU consultant — intubation thresholds agreed and documented.",
            "follow_up": "Respiratory team when stepping down.",
            "home_care_needs": "Asthma action plan later; not for discharge from ICU.",
        },
        "vitals": (37.0, 128, 70, 128, 28, 92),
    },
    {
        "mrn": "UHID-10035",
        "name": "Kiran Bhat",
        "age": 52,
        "sex": Sex.other,
        "ward": "Surgical Ward 1",
        "bed": "S1-15",
        "diagnosis": "Post-op thyroidectomy D1 — possible hypocalcaemia",
        "reason": "Total thyroidectomy for multinodular goitre, tingling hands overnight",
        "handover": "submitted",
        "risk": RiskLevel.watch,
        "sbar": {
            "current_situation": "D1 post total thyroidectomy. Voice hoarse but protecting airway. Perioral tingling. Ca 1.92 (corrected). Calcium gluconate infusion started.",
            "immediate_concern": "Airway haematoma and symptomatic hypocalcaemia — sit up, clip remover at bedside.",
            "critical_flag": False,
            "medical_history": [{"item": "Multinodular goitre", "notes": "Euthyroid pre-op"}],
            "surgical_history": [{"item": "Total thyroidectomy", "notes": "Yesterday, RLN identified both sides"}],
            "medications": [
                {"name": "Calcium gluconate 10%", "dose": "infusion", "route": "IV", "frequency": "per protocol", "notes": "Started 06:40"},
                {"name": "Levothyroxine", "dose": "100mcg", "route": "PO", "frequency": "OD", "notes": "Start D1"},
                {"name": "Alfacalcidol", "dose": "1mcg", "route": "PO", "frequency": "OD", "notes": "Started"},
            ],
            "nkda": True,
            "allergies": [],
            "system_exams": exams(
                respiratory={"status": "normal", "notes": "No stridor, neck not tense"},
                neurological={"status": "abnormal", "notes": "Positive Chvostek, tingling fingers"},
                integumentary={"status": "abnormal", "notes": "Collar incision, drain 20 ml"},
            ),
            "significant_findings": "No expanding haematoma. Drain 20 ml serosanguinous. Clip remover taped to head of bed.",
            "diagnostics": [
                {"test": "Corrected Ca", "result": "1.92 mmol/L", "date": str(date.today()), "abnormal": True},
                {"test": "PTH", "result": "pending", "date": str(date.today()), "abnormal": True},
            ],
            "immediate_treatment": "IV calcium, repeat Ca 4h, ENT if stridor.",
            "nursing_care": "Neck obs Q1H, voice, Chvostek, sit 30°, clip remover at bedside.",
            "team_communication": "Endocrine and ENT informed of Ca.",
            "follow_up": "Ca/PTH this evening; destine for endocrine OPD.",
            "home_care_needs": "Calcium tablets education if hypoparathyroidism persists.",
        },
        "vitals": (36.9, 118, 74, 90, 16, 98),
    },
]


def seed_if_empty(db: Session, *, include_census: bool | None = None) -> None:
    """Create users/wards on first run. Demo census only on first install (or when asked)."""
    first = not db.query(User).first()
    if first:
        _seed_core(db)
    else:
        _ensure_extra_staff(db)
    if include_census is True or (include_census is None and first):
        _ensure_census(db)
    _ensure_protocols_tasks(db)
    _ensure_demo_roster(db)
    db.commit()


def clear_clinical_data(db: Session) -> None:
    """Remove patients and all shift/handover work. Staff, wards, and logins stay."""
    db.query(AiUsageLog).delete()
    db.query(Escalation).delete()
    db.query(Task).delete()
    db.query(WardShiftSignoff).delete()
    db.query(Handover).delete()
    db.query(Admission).delete()
    db.query(Patient).delete()
    db.query(AuditLog).delete()
    db.commit()


def _ensure_demo_roster(db: Session) -> None:
    from app.deps import current_shift, next_shift, get_shift_assignment

    wards = _ward_by_name(db)
    by_email = {u.email: u for u in db.query(User).all()}
    assigner = by_email.get("supervisor.s1@hospital.local") or by_email.get("nursing.super@hospital.local")
    if not assigner:
        return
    st, sd = current_shift()
    nxt_st, nxt_sd = next_shift(st, sd)
    planned: list[tuple[Ward, ShiftType, date, User]] = []
    s1 = wards.get("Surgical Ward 1")
    anjali = by_email.get("nurse.s1@hospital.local")
    rohan = by_email.get("nurse.s1.in@hospital.local")
    if s1 and anjali:
        planned.append((s1, st, sd, anjali))
        planned.append((s1, ShiftType.morning, sd, anjali))
        if rohan:
            planned.append((s1, nxt_st, nxt_sd, rohan))
    med = wards.get("Medical Ward A")
    imran = by_email.get("nurse.med@hospital.local")
    if med and imran:
        planned.append((med, st, sd, imran))
    icu = wards.get("ICU")
    rhea = by_email.get("nurse.icu@hospital.local")
    if icu and rhea:
        planned.append((icu, st, sd, rhea))
    seen: set[tuple] = set()
    for ward, shift_type, shift_date, nurse in planned:
        key = (ward.id, shift_type, shift_date)
        if key in seen or get_shift_assignment(db, ward.id, shift_type, shift_date):
            continue
        seen.add(key)
        db.add(
            ShiftAssignment(
                ward_id=ward.id,
                shift_type=shift_type,
                shift_date=shift_date,
                nurse_id=nurse.id,
                assigned_by_id=assigner.id,
            )
        )
    db.flush()


def _ensure_extra_staff(db: Session) -> None:
    wards = _ward_by_name(db)
    extras = [
        ("nurse.icu@hospital.local", "NO03", "Staff Nurse Rhea D'Souza", Role.nursing_officer, "ICU"),
        ("supervisor.med@hospital.local", "SV02", "Sister Deepa Menon", Role.nursing_supervisor, None),
        ("nurse.s1.in@hospital.local", "NO04", "Staff Nurse Rohan Pillai", Role.nursing_officer, "Surgical Ward 1"),
    ]
    by_email = {u.email: u for u in db.query(User).all()}
    for email, emp, name, role, ward_name in extras:
        user = by_email.get(email)
        if not user:
            user = User(
                email=email,
                employee_id=emp,
                full_name=name,
                password_hash=hash_password(DEMO_PASSWORD),
                role=role,
            )
            db.add(user)
            db.flush()
            by_email[email] = user
        if ward_name and wards.get(ward_name):
            exists = (
                db.query(UserWardAssignment)
                .filter(UserWardAssignment.user_id == user.id, UserWardAssignment.ward_id == wards[ward_name].id)
                .first()
            )
            if not exists:
                db.add(UserWardAssignment(user_id=user.id, ward_id=wards[ward_name].id))
        if email == "supervisor.med@hospital.local":
            for wn in ("Medical Ward A", "ICU"):
                w = wards.get(wn)
                if not w:
                    continue
                exists = (
                    db.query(UserWardAssignment)
                    .filter(UserWardAssignment.user_id == user.id, UserWardAssignment.ward_id == w.id)
                    .first()
                )
                if not exists:
                    db.add(UserWardAssignment(user_id=user.id, ward_id=w.id))
    db.flush()


def _seed_core(db: Session) -> None:
    wards = [
        Ward(name="Surgical Ward 1", department="Surgical"),
        Ward(name="Surgical Ward 2", department="Surgical"),
        Ward(name="Medical Ward A", department="Medical"),
        Ward(name="ICU", department="Critical Care"),
    ]
    db.add_all(wards)
    db.flush()
    w1, w2, w3, w4 = wards

    users = [
        User(
            email="med.super@hospital.local",
            employee_id="MS001",
            full_name="Dr. Asha Menon",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.medical_superintendent,
        ),
        User(
            email="nursing.super@hospital.local",
            employee_id="NS001",
            full_name="Matron Priya Shah",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_superintendent,
        ),
        User(
            email="hod.surgical@hospital.local",
            employee_id="HOD01",
            full_name="Dr. Rahul Iyer",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.hod,
            department="Surgical",
        ),
        User(
            email="supervisor.s1@hospital.local",
            employee_id="SV01",
            full_name="Sister Kavita Rao",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_supervisor,
        ),
        User(
            email="nurse.s1@hospital.local",
            employee_id="NO01",
            full_name="Staff Nurse Anjali Nair",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_officer,
        ),
        User(
            email="nurse.med@hospital.local",
            employee_id="NO02",
            full_name="Staff Nurse Imran Khan",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_officer,
        ),
        User(
            email="nurse.s1.in@hospital.local",
            employee_id="NO04",
            full_name="Staff Nurse Rohan Pillai",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_officer,
        ),
        User(
            email="nurse.icu@hospital.local",
            employee_id="NO03",
            full_name="Staff Nurse Rhea D'Souza",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_officer,
        ),
        User(
            email="supervisor.med@hospital.local",
            employee_id="SV02",
            full_name="Sister Deepa Menon",
            password_hash=hash_password(DEMO_PASSWORD),
            role=Role.nursing_supervisor,
        ),
    ]
    db.add_all(users)
    db.flush()
    _ms, _ns, hod, sv, no1, no2, no1in, no3, sv2 = users
    db.add_all(
        [
            UserWardAssignment(user_id=hod.id, ward_id=w1.id),
            UserWardAssignment(user_id=hod.id, ward_id=w2.id),
            UserWardAssignment(user_id=sv.id, ward_id=w1.id),
            UserWardAssignment(user_id=sv.id, ward_id=w2.id),
            UserWardAssignment(user_id=no1.id, ward_id=w1.id),
            UserWardAssignment(user_id=no1in.id, ward_id=w1.id),
            UserWardAssignment(user_id=no2.id, ward_id=w3.id),
            UserWardAssignment(user_id=no3.id, ward_id=w4.id),
            UserWardAssignment(user_id=sv2.id, ward_id=w3.id),
            UserWardAssignment(user_id=sv2.id, ward_id=w4.id),
        ]
    )
    db.flush()


def _ward_by_name(db: Session) -> dict[str, Ward]:
    return {w.name: w for w in db.query(Ward).all()}


def _ensure_census(db: Session) -> None:
    wards = _ward_by_name(db)
    authors = {u.email: u for u in db.query(User).all()}
    no1 = authors.get("nurse.s1@hospital.local")
    no2 = authors.get("nurse.med@hospital.local")
    no3 = authors.get("nurse.icu@hospital.local")
    sv = authors.get("supervisor.s1@hospital.local")
    st, sd = current_shift()

    for row in CENSUS:
        ward = wards.get(row["ward"])
        if not ward:
            continue
        patient = db.query(Patient).filter(Patient.mrn == row["mrn"]).first()
        if not patient:
            patient = Patient(name=row["name"], age=row["age"], sex=row["sex"], mrn=row["mrn"])
            db.add(patient)
            db.flush()
        admission = (
            db.query(Admission)
            .filter(Admission.patient_id == patient.id, Admission.status == AdmissionStatus.active)
            .first()
        )
        if not admission:
            admission = Admission(
                patient_id=patient.id,
                ward_id=ward.id,
                bed_number=row["bed"],
                diagnosis=row["diagnosis"],
                reason_for_admission=row["reason"],
            )
            db.add(admission)
            db.flush()

        existing = (
            db.query(Handover)
            .filter(
                Handover.admission_id == admission.id,
                Handover.shift_type == st,
                Handover.shift_date == sd,
            )
            .first()
        )
        if existing:
            continue

        author = no1
        if row["ward"] == "Medical Ward A":
            author = no2
        elif row["ward"] == "ICU":
            author = no3
        status_map = {
            "draft": HandoverStatus.draft,
            "submitted": HandoverStatus.submitted,
            "accepted": HandoverStatus.accepted,
            "returned": HandoverStatus.returned,
        }
        sbar = dict(row["sbar"])
        t = row["vitals"]
        sbar["vitals"] = vitals(*t)
        status = status_map[row["handover"]]
        h = Handover(
            admission_id=admission.id,
            shift_type=st,
            shift_date=sd,
            author_id=author.id if author else no1.id,
            status=status,
            risk_level=row["risk"],
            diagnosis=row["diagnosis"],
            reason_for_admission=row["reason"],
            expected_discharge_date=row.get("discharge"),
            submitted_at=datetime.utcnow() if status != HandoverStatus.draft else None,
            reviewed_by_id=sv.id if status in (HandoverStatus.accepted, HandoverStatus.returned) and sv else None,
            reviewed_at=datetime.utcnow() if status in (HandoverStatus.accepted, HandoverStatus.returned) else None,
            review_comment=row.get("review_comment"),
            **{k: v for k, v in sbar.items() if k in Handover.__table__.c.keys()},
        )
        db.add(h)
        db.flush()

        if row["mrn"] == "UHID-10021" and not db.query(Escalation).filter(Escalation.handover_id == h.id).first():
            db.add(
                Escalation(
                    handover_id=h.id,
                    raised_by_id=author.id,
                    severity=EscalationSeverity.medium,
                    description="Drain output increasing vs last shift (was 15 ml). Please review.",
                )
            )
        if row["mrn"] == "UHID-10026":
            db.add(
                Escalation(
                    handover_id=h.id,
                    raised_by_id=author.id,
                    severity=EscalationSeverity.critical,
                    status=EscalationStatus.open,
                    description="DKA hour 8 — ketones still 1.1, FRIII running. Medical registrar to review before sign-off.",
                )
            )
        if row["mrn"] == "UHID-10034":
            db.add(
                Escalation(
                    handover_id=h.id,
                    raised_by_id=author.id,
                    severity=EscalationSeverity.critical,
                    description="Life-threatening asthma — pCO2 rising. Airway plan at bedside.",
                )
            )


def _ensure_protocols_tasks(db: Session) -> None:
    if not db.query(Protocol).first():
        hod = db.query(User).filter(User.email == "hod.surgical@hospital.local").first()
        w1 = db.query(Ward).filter(Ward.name == "Surgical Ward 1").first()
        w2 = db.query(Ward).filter(Ward.name == "Surgical Ward 2").first()
        db.add(
            Protocol(
                title="Surgical ward post-op handover checklist",
                body="Confirm drain, wound, analgesia, VTE, diet, mobilisation, pending labs, and next-of-kin update before submit.",
                created_by_id=hod.id,
                ward_ids=[w1.id, w2.id] if w1 and w2 else [],
            )
        )
        db.add(
            Protocol(
                title="Medical SBAR — sepsis and DKA flags",
                body="Any patient with critical risk, DKA protocol, or O2 >4 L must have immediate_concern completed and supervisor notified.",
                created_by_id=hod.id,
                ward_ids=[],
            )
        )
    if db.query(Task).count() < 3:
        sv = db.query(User).filter(User.email == "supervisor.s1@hospital.local").first()
        no1 = db.query(User).filter(User.email == "nurse.s1@hospital.local").first()
        no2 = db.query(User).filter(User.email == "nurse.med@hospital.local").first()
        p21 = db.query(Patient).filter(Patient.mrn == "UHID-10021").first()
        p26 = db.query(Patient).filter(Patient.mrn == "UHID-10026").first()
        p31 = db.query(Patient).filter(Patient.mrn == "UHID-10031").first()
        for patient, title, hours, assignee in [
            (p21, "Empty and chart drain at next round", 2, no1),
            (p26, "Hourly DKA chart — glucose, ketones, K+", 1, no2),
            (p31, "Daily weight before breakfast and strict I/O", 12, no2),
        ]:
            if not patient:
                continue
            adm = (
                db.query(Admission)
                .filter(Admission.patient_id == patient.id, Admission.status == AdmissionStatus.active)
                .first()
            )
            if not adm:
                continue
            db.add(
                Task(
                    admission_id=adm.id,
                    assignee_id=assignee.id if assignee else None,
                    created_by_id=sv.id if sv else assignee.id,
                    title=title,
                    due_at=datetime.utcnow() + timedelta(hours=hours),
                    priority="high",
                )
            )
