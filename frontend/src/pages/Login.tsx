import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { errorDetail } from "../api";
import AuthBrand from "./AuthBrand";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <AuthBrand />
        <h2>Sign in</h2>
        <p className="muted">Use your official email or employee ID. Access starts after approval.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await login(identifier, password);
            } catch (err) {
              const detail = errorDetail(err) as { code?: string; reason?: string; message?: string; queue?: string; submitted_at?: string } | undefined;
              if (detail && typeof detail === "object" && (detail.code === "pending" || detail.code === "rejected")) {
                navigate("/awaiting", { replace: true, state: detail });
                return;
              }
              setError(err instanceof Error ? err.message : "Login failed");
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="field">
            <label>Email or employee ID</label>
            <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 16 }}>
          New staff? <Link to="/signup">Create your account</Link>
        </p>
      </div>
    </div>
  );
}
