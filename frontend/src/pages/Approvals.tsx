import { useEffect, useState } from "react";
import { api, type ApprovalItem } from "../api";
import { formatIst } from "../clock";
import { useAuth } from "../auth";
import { notify, notifyError } from "../notify";

export default function Approvals() {
  const { user } = useAuth();
  const isSuper = user?.role === "nursing_superintendent";
  const [kind, setKind] = useState<"admins" | "nurses">(isSuper ? "admins" : "nurses");
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [count, setCount] = useState(0);
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const [error, setError] = useState("");

  const path = kind === "admins" ? "/approvals/admins" : "/approvals/nurses";

  const load = async () => {
    const res = await api.get<{ count: number; items: ApprovalItem[] }>(`${path}?status=${status}&q=${encodeURIComponent(q)}`);
    setItems(res.items);
    setCount(res.count);
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, status]);

  return (
    <>
      <div className="topbar">
        <h2>{kind === "admins" ? "Approval requests — Department Admins" : "Nurse requests — own department"}</h2>
      </div>
      {isSuper && (
        <div className="tabs">
          <button type="button" className={"tab" + (kind === "admins" ? " active" : "")} onClick={() => setKind("admins")}>
            Department Admins
          </button>
          <button type="button" className={"tab" + (kind === "nurses" ? " active" : "")} onClick={() => setKind("nurses")}>
            Nurses
          </button>
        </div>
      )}
      <div className="tabs">
        {["pending", "approved", "rejected"].map((s) => (
          <button key={s} type="button" className={"tab" + (status === s ? " active" : "")} onClick={() => setStatus(s)}>
            {s[0].toUpperCase() + s.slice(1)}
            {s === status ? ` (${count})` : ""}
          </button>
        ))}
      </div>
      <form
        className="inline"
        style={{ marginBottom: 16 }}
        onSubmit={(e) => {
          e.preventDefault();
          void load();
        }}
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={kind === "admins" ? "Search by name, department, employee ID" : "Search by name, nurse ID, ward"}
          style={{ minWidth: 260, minHeight: 44, borderRadius: 12, border: "1px solid var(--line)", padding: "0 12px" }}
        />
        <button className="btn" type="submit">
          Search
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      <div className="stack">
        {items.length === 0 && <p className="muted">No {status} requests.</p>}
        {items.map((row) => (
          <div className="card" key={row.id}>
            <strong>{row.full_name}</strong>
            <p className="muted">
              {row.department || "—"} · {row.employee_id}
              {row.ward_name ? ` · ${row.ward_name}` : ""}
            </p>
            <p className="muted">
              Requested {formatIst(row.created_at)} · {row.email} · {row.mobile || "—"}
            </p>
            {row.rejection_reason && <p className="error">{row.rejection_reason}</p>}
            {status === "pending" && (
              <div className="inline" style={{ marginTop: 10 }}>
                <button
                  type="button"
                  className="btn primary"
                  onClick={async () => {
                    setError("");
                    try {
                      await api.post(`/approvals/${row.id}/approve`);
                      notify("Request approved", `${row.full_name} can now sign in.`);
                      await load();
                    } catch (err) {
                      notifyError("Could not approve", err instanceof Error ? err.message : "Try again.");
                    }
                  }}
                >
                  Approve
                </button>
                <input
                  placeholder="Reject reason"
                  value={reasons[row.id] || ""}
                  onChange={(e) => setReasons((r) => ({ ...r, [row.id]: e.target.value }))}
                  style={{ minHeight: 44, borderRadius: 12, border: "1px solid var(--line)", padding: "0 12px" }}
                />
                <button
                  type="button"
                  className="btn"
                  onClick={async () => {
                    setError("");
                    try {
                      await api.post(`/approvals/${row.id}/reject`, { reason: reasons[row.id] || "Not approved" });
                      notify("Request rejected", `${row.full_name} was not granted access.`);
                      await load();
                    } catch (err) {
                      const text = err instanceof Error ? err.message : "Reject failed";
                      setError(text);
                      notifyError("Could not reject", text);
                    }
                  }}
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
