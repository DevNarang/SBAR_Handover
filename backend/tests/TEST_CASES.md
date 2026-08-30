# Test cases — SBAR Nursing Handover

Hospital-wide shifts are **Morning 07:00–14:00**, **Afternoon 14:00–21:00**, **Evening 21:00–07:00**.  
Handover is **nurse-to-nurse**: the outgoing nurse completes SBAR; the incoming nurse receives the ward for that shift.

Use these cases for QA. Expected results are the pass criteria.

---

## 1. Authentication and roles

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| AUTH-01 | Valid login | Enter email + `ChangeMe123!` | Lands on dashboard for that role |
| AUTH-02 | Invalid password | Wrong password | Error; no session |
| AUTH-03 | Lockout | Fail login 5 times | Account locked ~15 minutes |
| AUTH-04 | Session | Idle past timeout | Must log in again |
| AUTH-05 | Officer scope | Login `nurse.s1@hospital.local` | Only Surgical Ward 1 patients |
| AUTH-06 | Incoming officer | Login `nurse.s1.in@hospital.local` | Same ward, can **receive** Anjali’s shift |
| AUTH-07 | Medical officer | Login `nurse.med@hospital.local` | Medical Ward A only |
| AUTH-08 | ICU officer | Login `nurse.icu@hospital.local` | ICU only |
| AUTH-09 | Supervisor | Login `supervisor.s1@hospital.local` | Surgical wards 1–2; review + receive |
| AUTH-10 | HOD | Login `hod.surgical@hospital.local` | Surgical department wards |
| AUTH-11 | Superintendents | Med / Nursing super accounts | All wards, admin, analytics |
| AUTH-12 | Inactive user | Deactivate user in Admin, login | Rejected |

---

## 2. Shift model (morning / afternoon / evening)

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| SH-01 | Current shift | Open app during 07:00–14:00 | Shift chip = Morning |
| SH-02 | Afternoon window | 14:00–21:00 | Shift = Afternoon |
| SH-03 | Evening window | 21:00–07:00 | Shift = Evening; date is the date the evening shift **started** |
| SH-04 | Shift tabs | Ward board → Morning / Afternoon / Evening | Board filters SBAR notes for that shift + date |
| SH-05 | Isolated notes | Complete a Morning SBAR; open Afternoon | Afternoon list is empty/missing until started |
| SH-06 | Evening dark mode | Theme Auto on Evening shift | Dark theme on |
| SH-07 | Handover chain | Morning → Afternoon → Evening → next Morning | Incoming nurse always receives the **shift that just ended** |

---

## 3. Nurse-to-nurse handover (core flow)

Outgoing demo: **Anjali Nair** `nurse.s1@hospital.local`  
Incoming demo: **Rohan Pillai** `nurse.s1.in@hospital.local`

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| HO-01 | Outgoing prepares | Anjali logs in, Morning board, Start/Open SBAR for every patient | Each patient has a handover for this shift |
| HO-02 | Outgoing submits | Submit all SBARs with required fields | Status = submitted (or accepted if already reviewed) |
| HO-03 | Incoming cannot receive early | Rohan opens same Morning board while any note is draft/missing | **I receive this shift** disabled; incomplete count > 0 |
| HO-04 | Incoming receives | All notes submitted; Rohan selects outgoing nurse Anjali → Receive | Record: Anjali → Rohan, timestamp, patient count |
| HO-05 | Cannot receive own shift | Anjali tries to receive a shift she authored | Error: incoming ≠ outgoing |
| HO-06 | Double receive | Rohan receives again | Blocked; already handed over |
| HO-07 | Wrong outgoing nurse | Pick a nurse who did not write this shift’s notes | Error |
| HO-08 | Unassigned incoming | Officer from another ward tries receive | 403 / no ward access |
| HO-09 | Supervisor proxy | Supervisor receives on behalf of incoming staff, still names outgoing nurse | Allowed; audit shows supervisor as incoming signatory |
| HO-10 | Board after receive | Refresh board | Shows “Anjali handed this morning shift to Rohan” |
| HO-11 | Next shift work | Rohan starts Afternoon SBARs as **outgoing** for the following handover | New records; Morning notes stay read-only after accept/sign-off |
| HO-12 | Critical blocker | Patient is critical and not accepted/reviewed | Receive blocked until supervisor/incoming review |

---

## 4. Patient and admission (manual v1)

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| PAT-01 | Register | Patients → name, age, sex, optional MRN | Patient appears |
| PAT-02 | Admit | Ward, bed, diagnosis, reason | Active on that ward board |
| PAT-03 | Duplicate MRN | Same MRN twice | Should be unique / rejected or warned |
| PAT-04 | Transfer | Transfer to another ward/bed | Old admission transferred; new active admission |
| PAT-05 | Discharge | Discharge | Drops off active board; no new handover required |
| PAT-06 | Visibility | Officer admits to a ward they do not cover | Forbidden |

---

## 5. SBAR capture (parameters that must pass through)

Every submitted handover must persist and return:

**S:** name, age, sex, ward, bed, diagnosis, reason for admission, current situation, immediate concern  
**B:** medical history, surgical history, medications (name/dose/route/frequency), allergies or NKDA  
**A:** vitals (Temp, BP, PR, RR, SpO2), six system exams, significant findings, diagnostics  
**R:** immediate treatment, nursing care, team communication, expected discharge, follow-up, home care  

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| SBAR-01 | Save draft | Fill fields, leave page, reopen | Values unchanged |
| SBAR-02 | Structured rows | Add 2 meds + 1 allergy | Both round-trip |
| SBAR-03 | NKDA | Tick NKDA | Allergies not required |
| SBAR-04 | Submit incomplete | Submit empty draft | 400 listing missing fields |
| SBAR-05 | Submit complete | All required fields | Status submitted |
| SBAR-06 | Critical without concern | Critical flag on, empty immediate concern | Submit blocked |
| SBAR-07 | Vitals → watch | Temp 37.8 or SpO2 93 | Suggested risk = watch |
| SBAR-08 | Vitals → critical | SpO2 89 or SBP 70 | Suggested risk = critical |
| SBAR-09 | Override risk | Set critical + reason | Logged; badge updates |
| SBAR-10 | AI draft | AI draft (with Gemini key) | Inserts editable text; not auto-submitted |
| SBAR-11 | Voice | Voice into Situation | Transcript appended to that field |
| SBAR-12 | Edit after submit | Officer edits submitted note | Blocked until returned (officer) |
| SBAR-13 | Return | Supervisor returns with comment | Officer can edit and resubmit |

---

## 6. Review, tasks, escalation

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| REV-01 | Accept | Supervisor Accept | Status accepted |
| REV-02 | Return | Return + comment | Status returned; comment visible |
| ESC-01 | Flag | Escalate from SBAR | Appears on Escalations for that ward |
| ESC-02 | Resolve | Mark resolved | Leaves open queue |
| ESC-03 | Critical DKA/asthma | Open Lakshmi / Grace | Open critical escalation visible to supervisor+ |
| TSK-01 | Create / complete | Add task, mark done | Status done; overdue badge if past due |
| PRT-01 | Protocol | Officer opens SBAR | Sees ward protocol in Protocols |

---

## 7. Dashboards, reports, audit, admin

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| DASH-01 | Officer dashboard | Login officer | Own ward completion, tasks |
| DASH-02 | Super dashboard | Login superintendent | All four wards + compliance % |
| RPT-01 | Compliance | Reports | Completion, critical count, sign-off (received) per ward |
| AUD-01 | Audit | Login, submit, receive | login / update / submit / signoff rows |
| ADM-01 | Create user | Super creates officer + ward | New login works |
| ADM-02 | Create ward | Add ward + department tag | Appears for HOD filter |

---

## 8. Security and non-functionals

| ID | Flow | Steps | Expected |
|----|------|-------|----------|
| SEC-01 | Direct URL | Officer opens another ward’s handover ID | 403 |
| SEC-02 | Gemini key | Inspect browser network for AI | Key not in frontend |
| NFR-01 | Ward list | 15+ patients | Board loads < 2s locally |
| NFR-02 | Tablet | iPad / narrow window | 44px targets, usable board |
| OFF-01 | Offline | Disconnect network (v1) | App cannot save — **Phase 2**, not a v1 defect |

---

## 9. Suggested demo script (happy path)

1. Log in as **Anjali** (outgoing, morning).  
2. Complete and submit every Surgical Ward 1 SBAR.  
3. Log out. Log in as **Rohan** (incoming).  
4. Select **Morning** on the ward board.  
5. Choose outgoing nurse Anjali → **I receive this shift**.  
6. Confirm the banner: Anjali handed morning to Rohan.  
7. Switch to **Afternoon** and start the next outgoing notes.

---

## Demo accounts (password `ChangeMe123!`)

| Role | Email |
|------|--------|
| Outgoing nurse, Surgical 1 | `nurse.s1@hospital.local` |
| Incoming nurse, Surgical 1 | `nurse.s1.in@hospital.local` |
| Medical officer | `nurse.med@hospital.local` |
| ICU officer | `nurse.icu@hospital.local` |
| Supervisor surgical | `supervisor.s1@hospital.local` |
| Supervisor medical/ICU | `supervisor.med@hospital.local` |
| HOD Surgical | `hod.surgical@hospital.local` |
| Nursing Superintendent | `nursing.super@hospital.local` |
| Medical Superintendent | `med.super@hospital.local` |
