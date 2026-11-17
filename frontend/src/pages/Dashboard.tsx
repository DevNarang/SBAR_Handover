import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ROLE_LABEL } from "../api";
import { formatLocalNow } from "../clock";
import { useAuth } from "../auth";

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
  const { user } = useAuth();
  const [data, setData] = useState<Dash | null>(null);
  const [err, setErr] = useState("");
  const [clock, setClock] = useState(() => formatLocalNow());

  useEffect(() => {
    api.get<Dash>("/dashboard").then(setData).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => setClock(formatLocalNow()), 1000);
    return () => window.clearInterval(t);
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
        <p className="muted" style={{ margin: 0, textAlign: "right", fontWeight: 600 }}>
          {clock}
        </p>
      </div>
      {user && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="topbar" style={{ marginBottom: 12 }}>
            <div>
              <h3 style={{ margin: 0 }}>Your profile</h3>
              <p className="muted" style={{ margin: "4px 0 0" }}>
                Signed in as {user.full_name}
              </p>
            </div>
            <Link className="btn" to="/account">
              Edit profile
            </Link>
          </div>
          <dl className="profile-grid">
            <div>
              <dt>Name</dt>
              <dd>{user.full_name}</dd>
            </div>
            <div>
              <dt>Role</dt>
              <dd>
                {ROLE_LABEL[user.role] || user.role}
                {user.department ? ` - ${user.department}` : ""}
              </dd>
            </div>
            <div>
              <dt>Employee ID</dt>
              <dd>{user.employee_id}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{user.email}</dd>
            </div>
            <div>
              <dt>Department</dt>
              <dd>{user.department || "—"}</dd>
            </div>
            <div>
              <dt>Designation</dt>
              <dd>{user.designation || "—"}</dd>
            </div>
            <div>
              <dt>Mobile</dt>
              <dd>{user.mobile || "—"}</dd>
            </div>
            <div>
              <dt>Wards</dt>
              <dd>
                {user.ward_names?.length
                  ? user.ward_names.join(", ")
                  : ["nursing_superintendent", "medical_superintendent", "nursing_supervisor"].includes(user.role)
                    ? "All wards"
                    : "None assigned"}
              </dd>
            </div>
          </dl>
        </div>
      )}
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
