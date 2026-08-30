import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Ward } from "../api";
import { useAuth } from "../auth";

const SHIFTS = [
  { id: "morning", label: "Morning 07:00–14:00" },
  { id: "afternoon", label: "Afternoon 14:00–21:00" },
  { id: "evening", label: "Evening 21:00–07:00" },
];

type Board = {
  ward_id: number;
  shift_type: string;
  shift_date: string;
  patients: {
    admission_id: number;
    name: string;
    age: number;
    sex: string;
    bed_number: string;
    diagnosis: string;
    handover_id: number | null;
    status: string;
    risk_level: string;
    outgoing_nurse?: string | null;
  }[];
  outgoing_nurses: { id: number; full_name: string; handover_count: number }[];
  assigned_nurse: { id: number; full_name: string } | null;
  incoming_nurse: { id: number; full_name: string } | null;
  next_shift_type: string;
  next_shift_date: string;
  can_write: boolean;
  can_receive: boolean;
  signoff: {
    signed_at: string;
    notes: string | null;
    patient_count: number;
    signed_by_name?: string | null;
    outgoing_nurse_name?: string | null;
  } | null;
  blockers: { incomplete: unknown[]; critical_unreviewed: unknown[]; can_signoff: boolean };
};

export default function WardBoard() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [wards, setWards] = useState<Ward[]>([]);
  const [board, setBoard] = useState<Board | null>(null);
  const [notes, setNotes] = useState("");
  const [outgoingId, setOutgoingId] = useState<number | "">("");
  const [msg, setMsg] = useState("");
  const wardId = Number(params.get("ward") || user?.ward_ids[0] || 0);
  const shift = params.get("shift") || "";

  useEffect(() => {
    api.get<Ward[]>("/wards").then((w) => {
      setWards(w);
      if (!params.get("ward") && w[0]) {
        const next = new URLSearchParams(params);
        next.set("ward", String(w[0].id));
        setParams(next, { replace: true });
      }
    });
    if (!params.get("shift")) {
      api.get<{ shift_type: string }>("/meta/shift").then((m) => {
        const next = new URLSearchParams(params);
        next.set("shift", m.shift_type);
        setParams(next, { replace: true });
      });
    }
  }, []);

  useEffect(() => {
    if (!wardId || !shift) return;
    api
      .get<Board>(`/wards/${wardId}/board?shift_type=${shift}`)
      .then((b) => {
        setBoard(b);
        setOutgoingId(b.outgoing_nurses[0]?.id || "");
      })
      .catch((e) => setMsg(String(e)));
  }, [wardId, shift]);

  const canReceive = Boolean(board?.can_receive);

  async function openHandover(admissionId: number) {
    if (!board) return;
    const h = await api.post<{ id: number }>(
      `/handovers/ensure?admission_id=${admissionId}&shift_type=${board.shift_type}&shift_date=${board.shift_date}`,
    );
    window.location.href = `/handover/${h.id}`;
  }

  async function receiveHandover() {
    if (!board || !outgoingId) return;
    setMsg("");
    try {
      await api.post("/signoff", {
        ward_id: board.ward_id,
        shift_type: board.shift_type,
        shift_date: board.shift_date,
        outgoing_nurse_id: Number(outgoingId),
        notes,
      });
      setBoard(await api.get(`/wards/${wardId}/board?shift_type=${board.shift_type}`));
      setMsg("Shift received. Handover from outgoing nurse is complete.");
    } catch (e) {
      setMsg(String(e));
    }
  }

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set(key, value);
    setParams(next);
  }

  return (
    <>
      <div className="topbar">
        <div>
          <h2>Ward board</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {board ? `${board.shift_type} shift · ${board.shift_date}` : "Select a ward and shift"}
            {board?.assigned_nurse ? ` · On duty: ${board.assigned_nurse.full_name}` : " · No officer assigned"}
          </p>
        </div>
        <div className="inline">
          <select className="btn" value={wardId || ""} onChange={(e) => setParam("ward", e.target.value)}>
            {wards.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <select className="btn" value={shift} onChange={(e) => setParam("shift", e.target.value)}>
            {SHIFTS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {msg && <p className={msg.includes("received") ? "muted" : "error"}>{msg}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Bed</th>
              <th>Patient</th>
              <th>Diagnosis</th>
              <th>Outgoing nurse</th>
              <th>Risk</th>
              <th>Handover</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {board?.patients.map((p) => (
              <tr key={p.admission_id}>
                <td>{p.bed_number}</td>
                <td>
                  <strong>{p.name}</strong>
                  <div className="muted">
                    {p.age} / {p.sex}
                  </div>
                </td>
                <td>{p.diagnosis}</td>
                <td>{p.outgoing_nurse || "—"}</td>
                <td>
                  <span className={`badge ${p.risk_level}`}>{p.risk_level}</span>
                </td>
                <td>
                  <span className={`badge ${p.status}`}>{p.status.replace("_", " ")}</span>
                </td>
                <td>
                  {p.handover_id ? (
                    <Link className="btn" to={`/handover/${p.handover_id}`}>
                      {board.can_write && (p.status === "draft" || p.status === "returned" || p.status === "missing")
                        ? "Continue"
                        : "View"}
                    </Link>
                  ) : board.can_write ? (
                    <button className="btn primary" onClick={() => openHandover(p.admission_id)}>
                      Start SBAR
                    </button>
                  ) : (
                    <span className="muted">Read-only</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canReceive && board && (
        <div className="card" style={{ marginTop: 18 }}>
          <h3>Nurse-to-nurse handover</h3>
          {board.signoff ? (
            <p>
              <strong>{board.signoff.outgoing_nurse_name}</strong> handed this {board.shift_type} shift to{" "}
              <strong>{board.signoff.signed_by_name}</strong> at {new Date(board.signoff.signed_at).toLocaleString()} ·{" "}
              {board.signoff.patient_count} patients
            </p>
          ) : (
            <>
              <p className="muted">
                The officer assigned to this shift writes every SBAR. The officer assigned to the next shift (
                {board.next_shift_type} {board.next_shift_date}
                {board.incoming_nurse ? ` — ${board.incoming_nurse.full_name}` : ", not yet rostered"}) receives it and
                cannot change the previous note.
              </p>
              <p>
                Incomplete: {board.blockers.incomplete.length} · Critical unreviewed: {board.blockers.critical_unreviewed.length}
              </p>
              <div className="field">
                <label>Outgoing nurse (giving handover)</label>
                <select value={outgoingId} onChange={(e) => setOutgoingId(Number(e.target.value))}>
                  {board.outgoing_nurses.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.full_name} ({n.handover_count} notes)
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Incoming nurse notes</label>
                <textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Questions asked, patients walked round…" />
              </div>
              <button className="btn primary" disabled={!board.blockers.can_signoff || !outgoingId || !canReceive} onClick={receiveHandover}>
                I receive this shift
              </button>
              {!canReceive && (
                <p className="muted">Only the nurse assigned to the next shift (or a supervisor) can receive this handover.</p>
              )}
            </>
          )}
        </div>
      )}
    </>
  );
}
