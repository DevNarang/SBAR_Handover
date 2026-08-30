import { useEffect, useState } from "react";
import { api } from "../api";

type Row = { id: number; action: string; entity_type: string; entity_id: string; created_at: string; user_id: number | null };

export default function Audit() {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    api.get<Row[]>("/audit").then(setRows);
  }, []);
  return (
    <>
      <div className="topbar">
        <h2>Audit trail</h2>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>User</th>
              <th>Action</th>
              <th>Entity</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>{r.user_id ?? "—"}</td>
                <td>{r.action}</td>
                <td>{r.entity_type}</td>
                <td>{r.entity_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
