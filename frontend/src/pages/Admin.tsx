import { useEffect, useState } from "react";
import { api, ROLE_LABEL, type User, type Ward } from "../api";

export default function Admin() {
  const [users, setUsers] = useState<User[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [wardName, setWardName] = useState("");
  const [dept, setDept] = useState("Surgical");
  const [form, setForm] = useState({
    email: "",
    employee_id: "",
    full_name: "",
    password: "ChangeMe123!",
    role: "nursing_officer",
    department: "",
    ward_ids: [] as number[],
  });

  const load = async () => {
    setUsers(await api.get("/users"));
    setWards(await api.get("/wards"));
  };
  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      <div className="topbar">
        <h2>Hospital admin</h2>
      </div>
      <div className="grid cards">
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            await api.post("/users", form);
            await load();
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
        <form
          className="card"
          onSubmit={async (e) => {
            e.preventDefault();
            await api.post("/wards", { name: wardName, department: dept });
            setWardName("");
            await load();
          }}
        >
          <h3>Create ward</h3>
          <div className="field">
            <label>Name</label>
            <input value={wardName} onChange={(e) => setWardName(e.target.value)} required />
          </div>
          <div className="field">
            <label>Department tag</label>
            <input value={dept} onChange={(e) => setDept(e.target.value)} />
          </div>
          <button className="btn primary">Add ward</button>
        </form>
      </div>
      <div className="table-wrap" style={{ marginTop: 18 }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Email</th>
              <th>Active</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
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
