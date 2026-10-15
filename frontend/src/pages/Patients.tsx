import { useEffect, useMemo, useState } from "react";
import { api, type Ward } from "../api";
import { useAuth } from "../auth";
import { notify, notifyError } from "../notify";

type Patient = { id: number; name: string; age: number; sex: string; mrn: string | null };
type Admission = {
  id: number;
  patient_id: number;
  ward_id: number;
  bed_number: string;
  diagnosis: string;
  reason_for_admission: string;
  status: string;
  patient?: Patient;
  ward?: Ward;
};

export default function Patients() {
  const { user } = useAuth();
  const pickDeptFirst = user?.role === "nursing_superintendent" || user?.role === "medical_superintendent";
  const [patients, setPatients] = useState<Patient[]>([]);
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [department, setDepartment] = useState(user?.department || "");
  const [form, setForm] = useState({ name: "", age: 50, sex: "female", mrn: "" });
  const [adm, setAdm] = useState({ patient_id: 0, ward_id: 0, bed_number: "", diagnosis: "", reason_for_admission: "" });

  const departments = useMemo(() => {
    const names = new Set<string>();
    for (const w of wards) {
      const d = (w.department || "").trim();
      if (d) names.add(d);
    }
    return [...names].sort();
  }, [wards]);

  const wardChoices = pickDeptFirst
    ? wards.filter((w) => (w.department || "").trim() === department)
    : wards;

  async function reload() {
    const [p, a, w] = await Promise.all([
      api.get<Patient[]>("/patients"),
      api.get<Admission[]>("/admissions"),
      api.get<Ward[]>("/wards"),
    ]);
    setPatients(p);
    setAdmissions(a);
    setWards(w);
    setAdm((s) => ({
      ...s,
      patient_id: s.patient_id || p[0]?.id || 0,
      ward_id: pickDeptFirst
        ? w.some((row) => row.id === s.ward_id)
          ? s.ward_id
          : 0
        : s.ward_id || w[0]?.id || 0,
    }));
  }
  useEffect(() => {
    void reload();
  }, []);

  return (
    <>
      <div className="topbar">
        <h2>Patients & admissions</h2>
      </div>
      <div className="grid cards">
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api.post("/patients", { ...form, age: Number(form.age), mrn: form.mrn || null });
              notify("Patient added", `${form.name} is now on the hospital list.`);
              setForm({ name: "", age: 50, sex: "female", mrn: "" });
              await reload();
            } catch (err) {
              notifyError("Could not add patient", err instanceof Error ? err.message : "Try again.");
            }
          }}
        >
          <h3>Register patient</h3>
          <div className="field">
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="row">
            <div className="field">
              <label>Age</label>
              <input type="number" value={form.age} onChange={(e) => setForm({ ...form, age: Number(e.target.value) })} />
            </div>
            <div className="field">
              <label>Sex</label>
              <select value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value })}>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label>MRN / UHID (optional)</label>
            <input value={form.mrn} onChange={(e) => setForm({ ...form, mrn: e.target.value })} />
          </div>
          <button className="btn primary">Save patient</button>
        </form>
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!adm.ward_id) {
              notifyError("Choose a ward", pickDeptFirst ? "Select a department, then a ward." : "Select a ward.");
              return;
            }
            try {
              await api.post("/admissions", adm);
              const who = patients.find((p) => p.id === adm.patient_id)?.name || "Patient";
              const where = wards.find((w) => w.id === adm.ward_id)?.name || "ward";
              notify("Patient admitted", `${who} was admitted to ${where}, bed ${adm.bed_number}.`);
              await reload();
            } catch (err) {
              notifyError("Could not admit patient", err instanceof Error ? err.message : "Try again.");
            }
          }}
        >
          <h3>Admit to ward</h3>
          <div className="field">
            <label>Patient</label>
            <select value={adm.patient_id} onChange={(e) => setAdm({ ...adm, patient_id: Number(e.target.value) })}>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          {pickDeptFirst && (
            <div className="field">
              <label>Department</label>
              <select
                value={department}
                required
                onChange={(e) => {
                  const next = e.target.value;
                  setDepartment(next);
                  const first = wards.find((w) => (w.department || "").trim() === next);
                  setAdm({ ...adm, ward_id: first?.id || 0 });
                }}
              >
                <option value="">Select department</option>
                {departments.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="row">
            <div className="field">
              <label>Ward</label>
              <select
                value={adm.ward_id || ""}
                required
                disabled={pickDeptFirst && !department}
                onChange={(e) => setAdm({ ...adm, ward_id: Number(e.target.value) })}
              >
                <option value="">{pickDeptFirst && !department ? "Choose a department first" : "Select ward"}</option>
                {wardChoices.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Bed</label>
              <input value={adm.bed_number} onChange={(e) => setAdm({ ...adm, bed_number: e.target.value })} required />
            </div>
          </div>
          <div className="field">
            <label>Diagnosis</label>
            <input value={adm.diagnosis} onChange={(e) => setAdm({ ...adm, diagnosis: e.target.value })} required />
          </div>
          <div className="field">
            <label>Reason for admission</label>
            <textarea value={adm.reason_for_admission} onChange={(e) => setAdm({ ...adm, reason_for_admission: e.target.value })} required />
          </div>
          <button className="btn primary">Create admission</button>
        </form>
      </div>
      <div className="table-wrap" style={{ marginTop: 18 }}>
        <table>
          <thead>
            <tr>
              <th>Bed</th>
              <th>Patient</th>
              <th>Ward</th>
              <th>Diagnosis</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {admissions.map((a) => (
              <tr key={a.id}>
                <td>{a.bed_number}</td>
                <td>{a.patient?.name}</td>
                <td>{a.ward?.name}</td>
                <td>{a.diagnosis}</td>
                <td>
                  <button className="btn" onClick={async () => {
                    try {
                      await api.post(`/admissions/${a.id}/discharge`);
                      notify("Patient discharged", `${a.patient?.name || "Patient"} was discharged.`);
                      await reload();
                    } catch (err) {
                      notifyError("Could not discharge", err instanceof Error ? err.message : "Try again.");
                    }
                  }}>
                    Discharge
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
