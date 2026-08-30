import { useEffect, useState } from "react";
import { api, type Ward } from "../api";
import { useAuth } from "../auth";

type Protocol = { id: number; title: string; body: string; ward_ids: number[] };

export default function Protocols() {
  const { user } = useAuth();
  const [rows, setRows] = useState<Protocol[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const canCreate = ["hod", "nursing_superintendent", "medical_superintendent"].includes(user?.role || "");
  const load = () => api.get<Protocol[]>("/protocols").then(setRows);
  useEffect(() => {
    void load();
    api.get<Ward[]>("/wards").then(setWards);
  }, []);
  return (
    <>
      <div className="topbar">
        <h2>Protocols</h2>
      </div>
      {canCreate && (
        <form
          className="card"
          style={{ marginBottom: 16 }}
          onSubmit={async (e) => {
            e.preventDefault();
            await api.post("/protocols", { title, body, ward_ids: wards.map((w) => w.id) });
            setTitle("");
            setBody("");
            await load();
          }}
        >
          <div className="field">
            <label>Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>
          <div className="field">
            <label>Body</label>
            <textarea value={body} onChange={(e) => setBody(e.target.value)} required />
          </div>
          <button className="btn primary">Publish protocol</button>
        </form>
      )}
      <div className="stack">
        {rows.map((p) => (
          <div className="card" key={p.id}>
            <h3 style={{ color: "inherit", fontSize: 18 }}>{p.title}</h3>
            <p style={{ whiteSpace: "pre-wrap" }}>{p.body}</p>
          </div>
        ))}
      </div>
    </>
  );
}
