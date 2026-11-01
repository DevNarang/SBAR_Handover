import { useEffect, useState } from "react";
import { api, type Ward } from "../api";
import { useAuth } from "../auth";
import { notify, notifyError } from "../notify";
import { SHIFTS } from "../shifts";

type Officer = { id: number; full_name: string; email: string };
type Assignment = {
  id: number;
  ward_id: number;
  shift_type: string;
  shift_date: string;
  nurse_id: number;
  nurse_name: string | null;
};

function addDays(iso: string, n: number) {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

type AllocPatient = {
  admission_id: number;
  name: string;
  bed_number: string;
  nurse_id: number | null;
  nurse_name: string | null;
};

export default function Roster() {
  const { user } = useAuth();
  const canAssignPatients = ["hod", "nursing_supervisor", "medical_superintendent"].includes(user?.role || "");
  const [wards, setWards] = useState<Ward[]>([]);
  const [wardId, setWardId] = useState(0);
  const [officers, setOfficers] = useState<Officer[]>([]);
  const [rows, setRows] = useState<Assignment[]>([]);
  const [start, setStart] = useState("");
  const [msg, setMsg] = useState("");
  const [allocShift, setAllocShift] = useState("morning");
  const [allocDate, setAllocDate] = useState("");
  const [allocNurses, setAllocNurses] = useState<{ id: number; full_name: string }[]>([]);
  const [allocPatients, setAllocPatients] = useState<AllocPatient[]>([]);

  useEffect(() => {
    Promise.all([api.get<Ward[]>("/wards"), api.get<{ shift_date: string }>("/meta/shift")]).then(([w, m]) => {
      setWards(w);
      setWardId(w[0]?.id || 0);
      setStart(m.shift_date);
      setAllocDate(m.shift_date);
    });
  }, []);

  async function reload(id = wardId, from = start) {
    if (!id || !from) return;
    const end = addDays(from, 2);
    const [staff, assignments] = await Promise.all([
      api.get<Officer[]>(`/wards/${id}/officers`),
      api.get<Assignment[]>(`/shift-assignments?ward_id=${id}&start=${from}&end=${end}`),
    ]);
    setOfficers(staff);
    setRows(assignments);
  }

  useEffect(() => {
    void reload();
  }, [wardId, start]);

  const days = start ? [start, addDays(start, 1), addDays(start, 2)] : [];

  function assigned(date: string, shift: string) {
    return rows.filter((r) => r.shift_date === date && r.shift_type === shift);
  }

  async function addNurse(date: string, shift: string, nurseId: string) {
    if (!nurseId) return;
    setMsg("");
    try {
      await api.post("/shift-assignments", {
        ward_id: wardId,
        shift_type: shift,
        shift_date: date,
        nurse_id: Number(nurseId),
      });
      notify("Roster updated", `Officer added to ${shift} on ${date}.`);
      await reload();
    } catch (e) {
      notifyError("Roster not saved", String(e));
    }
  }

  async function removeNurse(id: number) {
    try {
      await api.delete(`/shift-assignments/${id}`);
      notify("Roster updated", "Officer removed from this shift.");
      await reload();
    } catch (e) {
      notifyError("Roster not saved", String(e));
    }
  }

  async function loadAlloc(date = allocDate, shift = allocShift) {
    if (!wardId || !date) return;
    const data = await api.get<{ nurses: { id: number; full_name: string }[]; patients: AllocPatient[] }>(
      `/patient-assignments?ward_id=${wardId}&shift_type=${shift}&shift_date=${date}`,
    );
    setAllocNurses(data.nurses);
    setAllocPatients(data.patients);
  }

  useEffect(() => {
    void loadAlloc();
  }, [wardId, allocDate, allocShift]);

  async function setPatientNurse(admissionId: number, nurseId: string) {
    try {
      await api.post("/patient-assignments", {
        admission_id: admissionId,
        shift_type: allocShift,
        shift_date: allocDate,
        nurse_id: nurseId ? Number(nurseId) : null,
      });
      notify("Patient allocated", nurseId ? "Nurse assigned for this shift." : "Patient left open for any rostered nurse.");
      await loadAlloc();
    } catch (e) {
      notifyError("Allocation not saved", String(e));
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h2>Shift roster</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Add the nurses covering each ward shift. Then allocate patients. An unassigned patient can be written by any nurse on that ward shift.
          </p>
        </div>
        <div className="inline">
          <select className="btn" value={wardId} onChange={(e) => setWardId(Number(e.target.value))}>
            {wards.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <input className="btn" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
      </div>
      {msg && <p className={msg.includes("saved") ? "muted" : "error"}>{msg}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Shift</th>
              {days.map((d) => (
                <th key={d}>{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {SHIFTS.map((s) => (
              <tr key={s.id}>
                <td>
                  <strong>{s.label.split(" ")[0]}</strong>
                  <div className="muted">{s.label.replace(/^\w+\s/, "")}</div>
                </td>
                {days.map((d) => {
                  const cell = assigned(d, s.id);
                  const taken = new Set(cell.map((r) => r.nurse_id));
                  return (
                    <td key={d}>
                      {cell.map((row) => (
                        <div key={row.id} className="inline" style={{ marginBottom: 6 }}>
                          <span>{row.nurse_name}</span>
                          <button className="btn" type="button" onClick={() => void removeNurse(row.id)}>
                            Remove
                          </button>
                        </div>
                      ))}
                      <select value="" onChange={(e) => void addNurse(d, s.id, e.target.value)}>
                        <option value="">Add nurse</option>
                        {officers
                          .filter((o) => !taken.has(o.id))
                          .map((o) => (
                            <option key={o.id} value={o.id}>
                              {o.full_name}
                            </option>
                          ))}
                      </select>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card" style={{ marginTop: 18 }}>
        <h3>Patient allocation</h3>
        <p className="muted">
          Department Admin, Nursing Supervisor, and Medical Superintendent assign each patient to one rostered nurse. Leave a patient blank and any nurse on this ward shift can write the SBAR.
        </p>
        <div className="inline">
          <select className="btn" value={allocShift} onChange={(e) => setAllocShift(e.target.value)}>
            {SHIFTS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <input className="btn" type="date" value={allocDate} onChange={(e) => setAllocDate(e.target.value)} />
        </div>
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                <th>Bed</th>
                <th>Patient</th>
                <th>Nurse</th>
              </tr>
            </thead>
            <tbody>
              {allocPatients.map((p) => (
                <tr key={p.admission_id}>
                  <td>{p.bed_number}</td>
                  <td>{p.name}</td>
                  <td>
                    {canAssignPatients ? (
                      <select value={p.nurse_id || ""} onChange={(e) => void setPatientNurse(p.admission_id, e.target.value)}>
                        <option value="">Any rostered nurse</option>
                        {allocNurses.map((n) => (
                          <option key={n.id} value={n.id}>
                            {n.full_name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      p.nurse_name || "Any rostered nurse"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
