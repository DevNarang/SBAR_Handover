import { useEffect, useState } from "react";
import { api, ROLE_LABEL, type User, type Ward } from "../api";
import { useAuth } from "../auth";
import { notify, notifyError } from "../notify";

export default function Admin() {
  const { user } = useAuth();
  const isHod = user?.role === "hod";
  const [users, setUsers] = useState<User[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [wardName, setWardName] = useState("");
  const [dept, setDept] = useState(user?.department || "");
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    email: "",
    employee_id: "",
    full_name: "",
    password: "",
    role: "nursing_officer",
    department: "",
    ward_ids: [] as number[],
  });

  const load = async () => {
    setWards(await api.get("/wards"));
    if (!isHod) setUsers(await api.get("/users"));
  };
  useEffect(() => {
    void load();
  }, [isHod]);

  useEffect(() => {
    if (isHod && user?.department) setDept(user.department);
  }, [isHod, user?.department]);

  return (
    <>
      <div className="topbar">
        <h2>{isHod ? "Department wards" : "Hospital admin"}</h2>
      </div>
      <div className="grid cards">
        {!isHod && (
          <form
            className="card"
            onSubmit={async (e) => {
              e.preventDefault();
              setError("");
              try {
                await api.post("/users", form);
                notify("User created", `${form.full_name} can sign in with the password you set.`);
                await load();
              } catch (err) {
                notifyError("Could not create user", err instanceof Error ? err.message : "Try again.");
              }
            }}
          >
            <h3>Create user</h3>
            {(["full_name", "email", "employee_id", "password"] as const).map((k) => (
              <div className="field" key={k}>
                <label>{k.replace("_", " ")}</label>
                <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} required />
              </div>
            ))}
            <div className="field">
              <label>Role</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {Object.entries(ROLE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Assigned wards (outgoing and incoming nurses must share a ward)</label>
              {wards.map((w) => (
                <label key={w.id} className="inline" style={{ marginTop: 6 }}>
                  <input
                    type="checkbox"
                    checked={form.ward_ids.includes(w.id)}
                    onChange={(e) => {
                      const next = e.target.checked
                        ? [...form.ward_ids, w.id]
                        : form.ward_ids.filter((id) => id !== w.id);
                      setForm({ ...form, ward_ids: next });
                    }}
                  />
                  {w.name}
                </label>
              ))}
            </div>
            <div className="field">
              <label>Department (HOD)</label>
              <input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
            </div>
            <button className="btn primary">Create</button>
          </form>
        )}
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            setError("");
            try {
              await api.post("/wards", { name: wardName, department: dept });
              notify("Ward added", `${wardName} (${dept}) is ready for nurse sign-up and rostering.`);
              setWardName("");
              await load();
            } catch (err) {
              const text = err instanceof Error ? err.message : "Could not add ward";
              setError(text);
              notifyError("Could not add ward", text);
            }
          }}
        >
          <h3>Create ward</h3>
          <p className="muted">
            {isHod
              ? "Nurses in your department can pick this ward when they sign up. Then you approve them and roster the shift."
              : "Department Admins and nurses use the department tag to find this ward."}
          </p>
          <div className="field">
            <label>Name</label>
            <input value={wardName} onChange={(e) => setWardName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Department</label>
            <input value={dept} onChange={(e) => setDept(e.target.value)} disabled={isHod} required />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary" disabled={isHod && !user?.department}>
            Add ward
          </button>
        </form>
      </div>
      <div className="table-wrap" style={{ marginTop: 18 }}>
        <table>
          <thead>
            <tr>
              {isHod ? (
                <>
                  <th>Ward</th>
                  <th>Department</th>
                  <th>Active</th>
                </>
              ) : (
                <>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Email</th>
                  <th>Active</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {isHod
              ? wards.map((w) => (
                  <tr key={w.id}>
                    <td>{w.name}</td>
                    <td>{w.department || "—"}</td>
                    <td>{w.is_active ? "Yes" : "No"}</td>
                  </tr>
                ))
              : users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.full_name}</td>
                    <td>{ROLE_LABEL[u.role]}</td>
                    <td>{u.email}</td>
                    <td>{u.is_active ? "Yes" : "No"}</td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
