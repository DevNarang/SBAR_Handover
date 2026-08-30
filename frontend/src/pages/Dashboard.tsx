import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Dash = {
  shift_type: string;
  shift_date: string;
  open_escalations: number;
  overdue_tasks: number;
  pending_reviews: number;
  wards: {
    ward_id: number;
    name: string;
    department: string | null;
    patients: number;
    submitted: number;
    accepted: number;
    critical: number;
    signed_off: boolean;
    completion_pct: number;
  }[];
};

export default function Dashboard() {
  const [data, setData] = useState<Dash | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get<Dash>("/dashboard").then(setData).catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="error">{err}</p>;
  if (!data) return <p className="muted">Loading dashboard…</p>;

  return (
    <>
      <div className="topbar">
        <div>
          <h2>Shift overview</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {data.shift_type} · {data.shift_date}
          </p>
        </div>
      </div>
      <div className="grid stats">
        <div className="card">
          <h3>Pending reviews</h3>
          <div className="stat">{data.pending_reviews}</div>
        </div>
        <div className="card">
          <h3>Open escalations</h3>
          <div className="stat">{data.open_escalations}</div>
        </div>
        <div className="card">
          <h3>Overdue tasks</h3>
          <div className="stat">{data.overdue_tasks}</div>
        </div>
        <div className="card">
          <h3>Wards in view</h3>
          <div className="stat">{data.wards.length}</div>
        </div>
      </div>
      <div className="grid cards" style={{ marginTop: 16 }}>
        {data.wards.map((w) => (
          <Link key={w.ward_id} to={`/ward?ward=${w.ward_id}`} className="card" style={{ color: "inherit" }}>
            <h3>
              {w.name} {w.department ? `· ${w.department}` : ""}
            </h3>
            <div className="stat">{w.completion_pct}%</div>
            <div className="progress" style={{ margin: "10px 0" }}>
              <span style={{ width: `${w.completion_pct}%` }} />
            </div>
            <p className="muted" style={{ margin: 0 }}>
              {w.submitted}/{w.patients} submitted · {w.critical} critical · {w.signed_off ? "Signed off" : "Awaiting sign-off"}
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}
