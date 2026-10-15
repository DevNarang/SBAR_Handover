import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type SignupOptions } from "../api";
import AuthBrand from "./AuthBrand";
import { notify } from "../notify";

export default function SignupAdmin() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<SignupOptions>({ departments: [], wards: [] });
  const [newDept, setNewDept] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    full_name: "",
    employee_id: "",
    email: "",
    mobile: "",
    department: "",
    new_department: "",
    designation: "",
    password: "",
    confirm_password: "",
  });

  useEffect(() => {
    void api.get<SignupOptions>("/auth/signup-options").then((opts) => {
      setOptions(opts);
      if (opts.departments.length === 0) setNewDept(true);
    });
  }, []);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <AuthBrand />
        <h2>Department Admin sign-up</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const res = await api.post<{ queue: string; submitted_at: string }>("/auth/signup", {
                kind: "department_admin",
                ...form,
                department: newDept ? "" : form.department,
                new_department: newDept ? form.new_department : "",
              });
              notify("Request submitted", "The Super Admin will review your Department Admin access.");
              navigate("/awaiting", { replace: true, state: { code: "pending", queue: res.queue, submitted_at: res.submitted_at } });
            } catch (err) {
              setError(err instanceof Error ? err.message : "Could not submit");
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="field">
            <label>Full name</label>
            <input value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required />
          </div>
          <div className="field">
            <label>Employee ID</label>
            <input value={form.employee_id} onChange={(e) => set("employee_id", e.target.value)} required />
          </div>
          <div className="field">
            <label>Official email</label>
            <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required />
          </div>
          <div className="field">
            <label>Mobile number</label>
            <input value={form.mobile} onChange={(e) => set("mobile", e.target.value)} required />
          </div>
          <div className="field">
            <label>Department</label>
            {!newDept ? (
              <select value={form.department} onChange={(e) => set("department", e.target.value)} required={options.departments.length > 0}>
                <option value="">Select department</option>
                {options.departments.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            ) : (
              <input value={form.new_department} onChange={(e) => set("new_department", e.target.value)} placeholder="New department name" required />
            )}
            <label className="inline" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={newDept} onChange={(e) => setNewDept(e.target.checked)} />
              Request a new department
            </label>
          </div>
          <div className="field">
            <label>Designation</label>
            <input value={form.designation} onChange={(e) => set("designation", e.target.value)} required />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required minLength={8} />
          </div>
          <div className="field">
            <label>Confirm password</label>
            <input type="password" value={form.confirm_password} onChange={(e) => set("confirm_password", e.target.value)} required />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "Submitting…" : "Request access"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 12 }}>
          Sent to Super Admin for approval. You cannot log in until approved.
        </p>
        <p className="muted">
          <Link to="/signup">Back to role selection</Link>
        </p>
      </div>
    </div>
  );
}
