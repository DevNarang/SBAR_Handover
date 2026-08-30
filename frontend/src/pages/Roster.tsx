import { useEffect, useState } from "react";
import { api, type Ward } from "../api";

const SHIFTS = [
  { id: "morning", label: "Morning 07:00–14:00" },
  { id: "afternoon", label: "Afternoon 14:00–21:00" },
  { id: "evening", label: "Evening 21:00–07:00" },
];

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

export default function Roster() {
  const [wards, setWards] = useState<Ward[]>([]);
  const [wardId, setWardId] = useState(0);
  const [officers, setOfficers] = useState<Officer[]>([]);
  const [rows, setRows] = useState<Assignment[]>([]);
  const [start, setStart] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    Promise.all([api.get<Ward[]>("/wards"), api.get<{ shift_date: string }>("/meta/shift")]).then(([w, m]) => {
      setWards(w);
      setWardId(w[0]?.id || 0);
      setStart(m.shift_date);
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
    return rows.find((r) => r.shift_date === date && r.shift_type === shift);
  }

  async function setNurse(date: string, shift: string, nurseId: string) {
    setMsg("");
    try {
      if (!nurseId) {
        const existing = assigned(date, shift);
        if (existing) await api.delete(`/shift-assignments/${existing.id}`);
      } else {
        await api.post("/shift-assignments", {
          ward_id: wardId,
          shift_type: shift,
          shift_date: date,
          nurse_id: Number(nurseId),
        });
      }
      await reload();
      setMsg("Roster saved.");
    } catch (e) {
      setMsg(String(e));
    }
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h2>Shift roster</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Assign which nursing officer covers each ward shift. Only that officer can write SBARs for the shift.
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
                  const row = assigned(d, s.id);
                  return (
                    <td key={d}>
                      <select value={row?.nurse_id || ""} onChange={(e) => void setNurse(d, s.id, e.target.value)}>
                        <option value="">Unassigned</option>
                        {officers.map((o) => (
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
    </>
  );
}
