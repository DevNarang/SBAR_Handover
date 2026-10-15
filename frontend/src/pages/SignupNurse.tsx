import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type SignupOptions } from "../api";
import AuthBrand from "./AuthBrand";
import { notify } from "../notify";

export default function SignupNurse() {
  const navigate = useNavigate();
  const [options, setOptions] = useState<SignupOptions>({ departments: [], wards: [] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    full_name: "",
    employee_id: "",
    email: "",
    mobile: "",
    department: "",
    ward_id: "",
    password: "",
    confirm_password: "",
  });

  useEffect(() => {
    void api.get<SignupOptions>("/auth/signup-options").then(setOptions);
  }, []);

  const wards = options.wards.filter((w) => !form.department || w.department === form.department);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <AuthBrand />
        <h2>Nurse sign-up</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const res = await api.post<{ queue: string; submitted_at: string }>("/auth/signup", {
                kind: "nurse",
                ...form,
                ward_id: Number(form.ward_id),
              });
              notify("Request submitted", "Your department Admin will review your access.");
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
            <label>Nurse / Employee ID</label>
            <input value={form.employee_id} onChange={(e) => set("employee_id", e.target.value)} required />
          </div>
          <div className="field">
            <label>Email</label>
            <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required />
          </div>
          <div className="field">
            <label>Mobile number</label>
            <input value={form.mobile} onChange={(e) => set("mobile", e.target.value)} required />
          </div>
          <div className="field">
            <label>Department</label>
            <select
              value={form.department}
              onChange={(e) => {
                set("department", e.target.value);
                set("ward_id", "");
              }}
              required
            >
              <option value="">Select department</option>
              {options.departments.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Ward / Unit</label>
            <select value={form.ward_id} onChange={(e) => set("ward_id", e.target.value)} required disabled={!form.department}>
              <option value="">{form.department ? "Select ward" : "Choose a department first"}</option>
              {wards.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
            {options.wards.length === 0 && <p className="muted">No wards yet. Ask the Super Admin to add a ward first.</p>}
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
          <button className="btn primary" disabled={busy || options.wards.length === 0} style={{ width: "100%" }}>
            {busy ? "Submitting…" : "Request to join"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 12 }}>
          Sent to your department Admin for approval. You cannot log in until approved.
        </p>
        <p className="muted">
          <Link to="/signup">Back to role selection</Link>
        </p>
      </div>
    </div>
  );
}
