import { useEffect, useState } from "react";
import { api } from "../api";

export default function Reports() {
  const [data, setData] = useState<{ wards: { name: string; completion_pct: number; signed_off: boolean; critical: number }[]; shift_type: string; shift_date: string } | null>(null);
  useEffect(() => {
    api.get<{ wards: { name: string; completion_pct: number; signed_off: boolean; critical: number }[]; shift_type: string; shift_date: string }>("/reports/compliance").then(setData);
  }, []);
  return (
    <>
      <div className="topbar">
        <div>
          <h2>Compliance</h2>
          <p className="muted">
            {data?.shift_type} · {data?.shift_date}
          </p>
        </div>
        <button className="btn" onClick={() => window.print()}>
          Print / PDF
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ward</th>
              <th>Completion</th>
              <th>Critical</th>
              <th>Sign-off</th>
            </tr>
          </thead>
          <tbody>
            {data?.wards.map((w) => (
              <tr key={w.name}>
                <td>{w.name}</td>
                <td>{w.completion_pct}%</td>
                <td>{w.critical}</td>
                <td>{w.signed_off ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
