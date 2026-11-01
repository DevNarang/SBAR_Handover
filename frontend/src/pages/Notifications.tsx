import { useEffect, useState } from "react";
import { api, downloadFile, type Ward } from "../api";
import { formatIst } from "../clock";
import { notifyError } from "../notify";

type Note = {
  id: number;
  kind: string;
  title: string;
  body: string;
  patient_id: number | null;
  patient_name: string | null;
  ward_id: number | null;
  ward_name: string | null;
  created_at: string | null;
  read: boolean;
};

type Patient = { id: number; name: string };

export default function Notifications() {
  const [rows, setRows] = useState<Note[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [wardId, setWardId] = useState("");
  const [patientId, setPatientId] = useState("");

  async function load(nextWard = wardId, nextPatient = patientId) {
    const q = new URLSearchParams();
    if (nextWard) q.set("ward_id", nextWard);
    if (nextPatient) q.set("patient_id", nextPatient);
    const suffix = q.toString() ? `?${q}` : "";
    setRows(await api.get<Note[]>(`/notifications${suffix}`));
  }

  useEffect(() => {
    api.get<Ward[]>("/wards").then(setWards);
    api.get<Patient[]>("/patients").then(setPatients);
  }, []);

  useEffect(() => {
    void load();
  }, [wardId, patientId]);

  return (
    <>
      <div className="topbar">
        <div>
          <h2>Notifications</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Admissions, handovers, critical vitals, escalations, due tasks, and roster changes. Filter by patient or ward, then download.
          </p>
        </div>
        <button
          className="btn primary"
          onClick={() => {
            const q = new URLSearchParams();
            if (wardId) q.set("ward_id", wardId);
            if (patientId) q.set("patient_id", patientId);
            const suffix = q.toString() ? `?${q}` : "";
            downloadFile(`/notifications/download.pdf${suffix}`, "notification-summary.pdf").catch((e) =>
              notifyError("Could not download", String(e)),
            );
          }}
        >
          Download PDF
        </button>
      </div>
      <div className="inline" style={{ marginBottom: 12 }}>
        <select className="btn" value={wardId} onChange={(e) => setWardId(e.target.value)}>
          <option value="">All wards</option>
          {wards.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <select className="btn" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
          <option value="">All patients</option>
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Summary</th>
              <th>Patient</th>
              <th>Ward</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.created_at ? formatIst(row.created_at) : "—"}</td>
                <td>
                  <strong>{row.title}</strong>
                  <div className="muted">{row.body}</div>
                </td>
                <td>{row.patient_name || "—"}</td>
                <td>{row.ward_name || "—"}</td>
                <td>
                  {row.read ? (
                    <span className="muted">Read</span>
                  ) : (
                    <button
                      className="btn"
                      onClick={async () => {
                        await api.post(`/notifications/${row.id}/read`);
                        await load();
                      }}
                    >
                      Mark read
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">
                  Nothing in this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
