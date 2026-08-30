import { useEffect, useState } from "react";
import { api, type Ward } from "../api";

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
  const [patients, setPatients] = useState<Patient[]>([]);
  const [admissions, setAdmissions] = useState<Admission[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [form, setForm] = useState({ name: "", age: 50, sex: "female", mrn: "" });
  const [adm, setAdm] = useState({ patient_id: 0, ward_id: 0, bed_number: "", diagnosis: "", reason_for_admission: "" });

  async function reload() {
    const [p, a, w] = await Promise.all([
      api.get<Patient[]>("/patients"),
      api.get<Admission[]>("/admissions"),
      api.get<Ward[]>("/wards"),
    ]);
    setPatients(p);
    setAdmissions(a);
    setWards(w);
    setAdm((s) => ({ ...s, patient_id: s.patient_id || p[0]?.id || 0, ward_id: s.ward_id || w[0]?.id || 0 }));
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
            await api.post("/patients", { ...form, age: Number(form.age), mrn: form.mrn || null });
            await reload();
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
            await api.post("/admissions", adm);
            await reload();
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
          <div className="row">
            <div className="field">
              <label>Ward</label>
              <select value={adm.ward_id} onChange={(e) => setAdm({ ...adm, ward_id: Number(e.target.value) })}>
                {wards.map((w) => (
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
                  <button className="btn" onClick={async () => { await api.post(`/admissions/${a.id}/discharge`); await reload(); }}>
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
