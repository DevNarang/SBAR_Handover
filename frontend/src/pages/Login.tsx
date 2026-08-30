import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";

const DEMOS = [
  ["med.super@hospital.local", "Medical Superintendent"],
  ["nursing.super@hospital.local", "Nursing Superintendent"],
  ["hod.surgical@hospital.local", "HOD Surgical"],
  ["supervisor.s1@hospital.local", "Supervisor"],
  ["nurse.s1@hospital.local", "Nursing Officer (Surgical 1)"],
];

export default function Login() {
  const { user, login } = useAuth();
  const [identifier, setIdentifier] = useState("nurse.s1@hospital.local");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark">
            <img src="/aiims-bibinagar.png" alt="AIIMS Bibinagar emblem" />
          </div>
          <div>
            <h1>SBAR Handover</h1>
            <p>All India Institute of Medical Sciences (AIIMS) - Bibinagar, Hyderabad</p>
          </div>
        </div>
        <h2>Sign in</h2>
        <p className="muted">Local staff accounts. Use your hospital email or employee ID.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await login(identifier, password);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Login failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="field">
            <label>Email or employee ID</label>
            <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Signing in…" : "Enter ward"}
          </button>
        </form>
        <div className="demo">
          <strong>Demo password:</strong> ChangeMe123!
          <div className="stack" style={{ marginTop: 8 }}>
            {DEMOS.map(([email, label]) => (
              <button key={email} type="button" className="btn" onClick={() => setIdentifier(email)}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
