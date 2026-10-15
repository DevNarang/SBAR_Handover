import { useEffect, useState } from "react";
import { api } from "../api";
import { notify, notifyError } from "../notify";

type Task = {
  id: number;
  title: string;
  status: string;
  priority: string;
  due_at: string | null;
  patient_name: string | null;
  overdue: boolean;
  admission_id: number;
};

export default function Tasks() {
  const [rows, setRows] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const load = () => api.get<Task[]>("/tasks").then(setRows);
  useEffect(() => {
    void load();
  }, []);
  return (
    <>
      <div className="topbar">
        <h2>Tasks</h2>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="inline">
          <input placeholder="New task title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button
            className="btn primary"
            onClick={async () => {
              const first = rows[0];
              if (!title || !first) return;
              try {
                await api.post("/tasks", { admission_id: first.admission_id, title, priority: "medium" });
                notify("Task added", title);
                setTitle("");
                await load();
              } catch (err) {
                notifyError("Could not add task", err instanceof Error ? err.message : "Try again.");
              }
            }}
          >
            Add on first patient
          </button>
        </div>
        <p className="muted">Tip: create patient-specific tasks from the ward after at least one task exists, or from Recommendation follow-up.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Task</th>
              <th>Patient</th>
              <th>Priority</th>
              <th>Due</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td>{t.title}</td>
                <td>{t.patient_name}</td>
                <td>{t.priority}</td>
                <td>{t.due_at ? new Date(t.due_at).toLocaleString() : "—"} {t.overdue && <span className="badge critical">overdue</span>}</td>
                <td>
                  <select
                    value={t.status}
                    onChange={async (e) => {
                      try {
                        await api.patch(`/tasks/${t.id}`, { status: e.target.value });
                        notify("Task updated", `${t.title} is now ${e.target.value.replace("_", " ")}.`);
                        await load();
                      } catch (err) {
                        notifyError("Could not update task", err instanceof Error ? err.message : "Try again.");
                      }
                    }}
                  >
                    <option value="pending">Pending</option>
                    <option value="in_progress">In progress</option>
                    <option value="done">Done</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
