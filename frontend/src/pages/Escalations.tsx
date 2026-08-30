import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";

type Esc = {
  id: number;
  severity: string;
  status: string;
  description: string;
  patient_name: string;
  created_at: string;
};

const CAN_RESOLVE = ["nursing_supervisor", "hod", "nursing_superintendent", "medical_superintendent"];

export default function Escalations() {
  const { user } = useAuth();
  const [rows, setRows] = useState<Esc[]>([]);
  const [msg, setMsg] = useState("");
  const canResolve = CAN_RESOLVE.includes(user?.role || "");
  const load = () => api.get<Esc[]>("/escalations").then(setRows);
  useEffect(() => {
    void load();
  }, []);
  return (
    <>
      <div className="topbar">
        <h2>Escalations</h2>
      </div>
      {msg && <p className="error">{msg}</p>}
      <div className="stack">
        {rows.map((e) => (
          <div className="card" key={e.id}>
            <div className="inline">
              <span className={`badge ${e.severity === "critical" ? "critical" : "watch"}`}>{e.severity}</span>
              <span className={`badge ${e.status}`}>{e.status}</span>
              <strong>{e.patient_name}</strong>
              <span className="muted">{new Date(e.created_at).toLocaleString()}</span>
            </div>
            <p>{e.description}</p>
            {e.status !== "resolved" && canResolve && (
              <button
                className="btn"
                onClick={async () => {
                  setMsg("");
                  await api.patch(`/escalations/${e.id}`, { status: "resolved", resolution_notes: "Resolved on ward" });
                  await load();
                }}
              >
                Mark resolved
              </button>
            )}
            {e.status !== "resolved" && !canResolve && (
              <p className="muted">A supervisor must resolve this escalation.</p>
            )}
          </div>
        ))}
        {!rows.length && <p className="muted">No escalations in your wards.</p>}
      </div>
    </>
  );
}
