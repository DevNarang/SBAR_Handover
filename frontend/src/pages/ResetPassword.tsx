import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import AuthBrand from "./AuthBrand";
import PasswordField from "../PasswordField";
import { notify, notifyError } from "../notify";

export default function ResetPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <AuthBrand />
        <h2>Reset password</h2>
        <p className="muted">Enter the email and employee ID on your account, then choose a new password.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api.post("/auth/reset-password", {
                email,
                employee_id: employeeId,
                new_password: password,
                confirm_password: confirm,
              });
              notify("Password reset", "Sign in with your new password.");
              navigate("/login", { replace: true });
            } catch (err) {
              const text = err instanceof Error ? err.message : "Could not reset password";
              setError(text);
              notifyError("Could not reset password", text);
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="field">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </div>
          <div className="field">
            <label>Employee ID</label>
            <input value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} required />
          </div>
          <div className="field">
            <label>New password</label>
            <PasswordField value={password} onChange={setPassword} required minLength={8} autoComplete="new-password" />
          </div>
          <div className="field">
            <label>Confirm new password</label>
            <PasswordField value={confirm} onChange={setConfirm} required minLength={8} autoComplete="new-password" />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Saving…" : "Reset password"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/login">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}
