import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { nowIstIso } from "../clock";
import { notify, notifyError } from "../notify";
import { useAuth } from "../auth";

type Handover = Record<string, unknown> & {
  id: number;
  status: string;
  risk_level: string;
  suggested_risk: string;
  author_name?: string | null;
  can_edit?: boolean;
  lock_reason?: string | null;
  previous_handover_id?: number | null;
  previous_author_name?: string | null;
  previous_shift_type?: string | null;
  previous_shift_date?: string | null;
  patient?: { name: string; age: number; sex: string; mrn?: string };
  admission?: { bed_number: string; ward_name: string; diagnosis: string };
};

const SYSTEMS = [
  "respiratory",
  "cardiovascular",
  "neurological",
  "genitourinary",
  "musculoskeletal",
  "integumentary",
];

const TABS = ["S", "B", "A", "R"] as const;

export default function HandoverForm() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [h, setH] = useState<Handover | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]>("S");
  const [msg, setMsg] = useState("");
  const [voiceField, setVoiceField] = useState("current_situation");
  const recRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    api.get<Handover>(`/handovers/${id}`).then(setH).catch((e) => setMsg(String(e)));
  }, [id]);

  async function save(patch: Record<string, unknown>) {
    if (!h || h.can_edit === false) return;
    const next = { ...h, ...patch };
    setH(next as Handover);
    const saved = await api.patch<Handover>(`/handovers/${h.id}`, patch);
    setH(saved);
  }

  function setField(key: string, value: unknown) {
    void save({ [key]: value });
  }

  async function submit() {
    setMsg("");
    try {
      const saved = await api.post<Handover>(`/handovers/${h!.id}/submit`);
      setH(saved);
      const name = saved.patient?.name || "patient";
      const bed = saved.admission?.bed_number ? ` · Bed ${saved.admission.bed_number}` : "";
      const text = `SBAR submitted for ${name}${bed}. The incoming nurse can view it but cannot change this note.`;
      setMsg(text);
      notify("SBAR submitted", text);
    } catch (e) {
      const text = String(e);
      setMsg(text);
      notifyError("Could not submit SBAR", text);
    }
  }

  async function review(action: "accept" | "return") {
    const saved = await api.post<Handover>(`/handovers/${h!.id}/review`, { action, comment: h?.review_comment });
    setH(saved);
    notify(action === "accept" ? "SBAR accepted" : "SBAR returned", saved.patient?.name || "Handover updated.");
  }

  async function aiDraft() {
    setMsg("Generating AI draft…");
    const r = await api.post<{ draft: string }>(`/ai/summary`, { handover_id: h!.id, payload: {} });
    try {
      const parsed = JSON.parse(r.draft.replace(/```json|```/g, "").trim());
      await save({
        current_situation: parsed.current_situation ?? h!.current_situation,
        significant_findings: parsed.significant_findings ?? h!.significant_findings,
        immediate_treatment: parsed.immediate_treatment ?? h!.immediate_treatment,
        nursing_care: parsed.nursing_care ?? h!.nursing_care,
      });
      setMsg("AI draft inserted. Review before submit — never auto-saved as final.");
      notify("AI draft inserted", "Review the fields before you submit. This is not the final SBAR.");
    } catch {
      setMsg(r.draft);
    }
  }

  async function recordVoice() {
    if (recRef.current) {
      recRef.current.stop();
      recRef.current = null;
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      const fd = new FormData();
      fd.append("file", blob, "note.webm");
      const r = await api.post<{ text: string }>(`/ai/voice?handover_id=${h!.id}`, fd);
      const prev = String(h?.[voiceField] || "");
      await save({ [voiceField]: (prev ? prev + " " : "") + r.text });
      setMsg("Voice inserted into " + voiceField);
      notify("Voice added", `Inserted into ${voiceField.replaceAll("_", " ")}.`);
    };
    rec.start();
    recRef.current = rec;
    setMsg("Recording… tap Voice again to stop.");
  }

  if (!h) return <p className="muted">Loading SBAR…</p>;
  const readOnly = h.can_edit === false;
  const p = h.patient;
  const vitals = (h.vitals as Record<string, number>) || {};
  const exams = (h.system_exams as Record<string, { status: string; notes: string }>) || {};
  const reviewer = ["nursing_supervisor", "hod", "nursing_superintendent", "medical_superintendent"].includes(user?.role || "");

  return (
    <>
      <div className="topbar">
        <div>
          <h2>
            {p?.name} · Bed {h.admission?.bed_number}
          </h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {p?.age} / {p?.sex} · {h.admission?.ward_name} · {String(h.shift_type)} {String(h.shift_date)}
            {h.author_name ? ` · Written by ${h.author_name}` : ""}
          </p>
        </div>
        <div className="chips">
          <span className={`badge ${h.risk_level}`}>{String(h.risk_level)}</span>
          <span className={`badge ${h.status}`}>{String(h.status).replace("_", " ")}</span>
          <span className="chip">Suggested: {h.suggested_risk}</span>
          <button className="btn" onClick={() => nav("/ward")}>
            Back
          </button>
        </div>
      </div>

      {readOnly && (
        <p className="muted" style={{ marginBottom: 12 }}>
          {h.lock_reason || "This SBAR is read-only."} Open your assigned shift to carry these details into your own outgoing SBAR.
        </p>
      )}
      {!readOnly && h.previous_author_name && (
        <p className="notice ok" style={{ marginBottom: 12 }}>
          Details below were carried forward from {h.previous_author_name}'s {h.previous_shift_type} shift
          {h.previous_shift_date ? ` (${h.previous_shift_date})` : ""}. Edit anything that has changed, then submit as your outgoing SBAR.
        </p>
      )}

      {!readOnly && (
      <div className="inline" style={{ marginBottom: 12 }}>
        <button className="btn primary" onClick={aiDraft}>
          AI draft
        </button>
        <select className="btn" value={voiceField} onChange={(e) => setVoiceField(e.target.value)}>
          <option value="current_situation">Voice → Situation</option>
          <option value="immediate_concern">Voice → Concern</option>
          <option value="significant_findings">Voice → Findings</option>
          <option value="nursing_care">Voice → Nursing care</option>
        </select>
        <button className="btn" onClick={recordVoice}>
          Voice
        </button>
      </div>
      )}
      {msg && (
        <p className={msg.toLowerCase().includes("error") || msg.includes("missing") ? "error" : msg.toLowerCase().includes("submitted") ? "notice ok" : "muted"}>
          {msg}
        </p>
      )}

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={"tab" + (tab === t ? " active" : "")} onClick={() => setTab(t)}>
            {t === "S" ? "Situation" : t === "B" ? "Background" : t === "A" ? "Assessment" : "Recommendation"}
          </button>
        ))}
      </div>

      <fieldset disabled={readOnly} style={{ border: 0, margin: 0, padding: 0, minInlineSize: "auto" }}>

      {tab === "S" && (
        <div className="card stack">
          <div className="row">
            <div className="field">
              <label>Diagnosis</label>
              <input value={String(h.diagnosis || "")} onChange={(e) => setH({ ...h, diagnosis: e.target.value })} onBlur={(e) => setField("diagnosis", e.target.value)} />
            </div>
            <div className="field">
              <label>Risk override</label>
              <select
                value={String(h.risk_level)}
                onChange={(e) => save({ risk_level: e.target.value, risk_override_reason: h.risk_override_reason || "Manual override" })}
              >
                <option value="stable">Stable</option>
                <option value="watch">Watch</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div className="field">
            <label>Reason for admission</label>
            <textarea value={String(h.reason_for_admission || "")} onBlur={(e) => setField("reason_for_admission", e.target.value)} onChange={(e) => setH({ ...h, reason_for_admission: e.target.value })} />
          </div>
          <div className="field">
            <label>Current situation</label>
            <textarea value={String(h.current_situation || "")} onBlur={(e) => setField("current_situation", e.target.value)} onChange={(e) => setH({ ...h, current_situation: e.target.value })} />
          </div>
          <label className="inline">
            <input type="checkbox" checked={Boolean(h.critical_flag)} onChange={(e) => save({ critical_flag: e.target.checked })} />
            Flag immediate concern as critical
          </label>
          <div className="field">
            <label>Immediate concern</label>
            <textarea value={String(h.immediate_concern || "")} onBlur={(e) => setField("immediate_concern", e.target.value)} onChange={(e) => setH({ ...h, immediate_concern: e.target.value })} />
          </div>
        </div>
      )}

      {tab === "B" && (
        <div className="card stack">
          <ListEditor label="Medical history" rows={(h.medical_history as { item: string; notes: string }[]) || []} onChange={(rows) => save({ medical_history: rows })} />
          <ListEditor label="Surgical history" rows={(h.surgical_history as { item: string; notes: string }[]) || []} onChange={(rows) => save({ surgical_history: rows })} />
          <MedEditor rows={(h.medications as Record<string, string>[]) || []} onChange={(rows) => save({ medications: rows })} />
          <label className="inline">
            <input type="checkbox" checked={Boolean(h.nkda)} onChange={(e) => save({ nkda: e.target.checked, allergies: e.target.checked ? [] : h.allergies })} />
            NKDA — no known drug allergies
          </label>
          {!h.nkda && (
            <AllergyEditor rows={(h.allergies as Record<string, string>[]) || []} onChange={(rows) => save({ allergies: rows })} />
          )}
        </div>
      )}

      {tab === "A" && (
        <div className="card stack">
          <div className="row">
            {(["temp", "bp_systolic", "bp_diastolic", "pr", "rr", "spo2"] as const).map((k) => (
              <div className="field" key={k}>
                <label>{k.replace("_", " ").toUpperCase()}</label>
                <input
                  type="number"
                  value={vitals[k] ?? ""}
                  onChange={(e) => {
                    const next = { ...vitals, [k]: e.target.value === "" ? null : Number(e.target.value), recorded_at: nowIstIso() };
                    setH({ ...h, vitals: next });
                  }}
                  onBlur={() => save({ vitals })}
                />
              </div>
            ))}
          </div>
          {SYSTEMS.map((sys) => {
            const ex = exams[sys] || { status: "normal", notes: "" };
            return (
              <div key={sys} className="row">
                <div className="field">
                  <label>{sys}</label>
                  <select
                    value={ex.status}
                    onChange={(e) => save({ system_exams: { ...exams, [sys]: { ...ex, status: e.target.value } } })}
                  >
                    <option value="normal">Normal</option>
                    <option value="abnormal">Abnormal</option>
                  </select>
                </div>
                <div className="field">
                  <label>Notes</label>
                  <input
                    value={ex.notes}
                    onChange={(e) => {
                      const next = { ...exams, [sys]: { ...ex, notes: e.target.value } };
                      setH({ ...h, system_exams: next });
                    }}
                    onBlur={() => save({ system_exams: exams })}
                  />
                </div>
              </div>
            );
          })}
          <div className="field">
            <label>Significant findings</label>
            <textarea value={String(h.significant_findings || "")} onChange={(e) => setH({ ...h, significant_findings: e.target.value })} onBlur={(e) => setField("significant_findings", e.target.value)} />
          </div>
        </div>
      )}

      {tab === "R" && (
        <div className="card stack">
          <div className="field">
            <label>Immediate treatment</label>
            <textarea value={String(h.immediate_treatment || "")} onChange={(e) => setH({ ...h, immediate_treatment: e.target.value })} onBlur={(e) => setField("immediate_treatment", e.target.value)} />
          </div>
          <div className="field">
            <label>Nursing care required</label>
            <textarea value={String(h.nursing_care || "")} onChange={(e) => setH({ ...h, nursing_care: e.target.value })} onBlur={(e) => setField("nursing_care", e.target.value)} />
          </div>
          <div className="field">
            <label>Team communication</label>
            <textarea value={String(h.team_communication || "")} onChange={(e) => setH({ ...h, team_communication: e.target.value })} onBlur={(e) => setField("team_communication", e.target.value)} />
          </div>
          <div className="row">
            <div className="field">
              <label>Expected discharge</label>
              <input type="date" value={String(h.expected_discharge_date || "")} onChange={(e) => save({ expected_discharge_date: e.target.value || null })} />
            </div>
            <div className="field">
              <label>Follow-up</label>
              <input value={String(h.follow_up || "")} onChange={(e) => setH({ ...h, follow_up: e.target.value })} onBlur={(e) => setField("follow_up", e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label>Home care needs</label>
            <textarea value={String(h.home_care_needs || "")} onChange={(e) => setH({ ...h, home_care_needs: e.target.value })} onBlur={(e) => setField("home_care_needs", e.target.value)} />
          </div>
        </div>
      )}
      </fieldset>

      <div className="inline" style={{ marginTop: 16 }}>
        {!readOnly && h.status !== "accepted" && (
          <button className="btn primary" onClick={submit}>
            Submit handover
          </button>
        )}
        {reviewer && (h.status === "submitted" || h.status === "under_review") && (
          <>
            <button className="btn" onClick={() => review("accept")}>
              Accept
            </button>
            <button className="btn danger" onClick={() => review("return")}>
              Return
            </button>
          </>
        )}
        <EscalateButton handoverId={h.id} />
      </div>
    </>
  );
}

function EscalateButton({ handoverId }: { handoverId: number }) {
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState("");
  return (
    <>
      <button className="btn" onClick={() => setOpen(!open)}>
        Escalate
      </button>
      {open && (
        <div className="card" style={{ width: "100%" }}>
          <div className="field">
            <label>Escalation note</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <button
            className="btn danger"
            onClick={async () => {
              await api.post("/escalations", { handover_id: handoverId, severity: "high", description });
              setOpen(false);
              notify("Escalation sent", "A supervisor can now review this from Escalations.");
            }}
          >
            Send to supervisor
          </button>
        </div>
      )}
    </>
  );
}

function ListEditor({
  label,
  rows,
  onChange,
}: {
  label: string;
  rows: { item: string; notes: string }[];
  onChange: (rows: { item: string; notes: string }[]) => void;
}) {
  return (
    <div>
      <strong>{label}</strong>
      {rows.map((r, i) => (
        <div className="row" key={i} style={{ marginTop: 8 }}>
          <input value={r.item} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, item: e.target.value } : x)))} placeholder="Item" />
          <input value={r.notes} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, notes: e.target.value } : x)))} placeholder="Notes" />
        </div>
      ))}
      <button className="btn" style={{ marginTop: 8 }} onClick={() => onChange([...rows, { item: "", notes: "" }])}>
        Add
      </button>
    </div>
  );
}

function MedEditor({ rows, onChange }: { rows: Record<string, string>[]; onChange: (r: Record<string, string>[]) => void }) {
  return (
    <div>
      <strong>Current medications</strong>
      {rows.map((r, i) => (
        <div className="row" key={i} style={{ marginTop: 8, gridTemplateColumns: "2fr 1fr 1fr 1fr" }}>
          {["name", "dose", "route", "frequency"].map((k) => (
            <input key={k} placeholder={k} value={r[k] || ""} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))} />
          ))}
        </div>
      ))}
      <button className="btn" style={{ marginTop: 8 }} onClick={() => onChange([...rows, { name: "", dose: "", route: "", frequency: "", notes: "" }])}>
        Add medication
      </button>
    </div>
  );
}

function AllergyEditor({ rows, onChange }: { rows: Record<string, string>[]; onChange: (r: Record<string, string>[]) => void }) {
  return (
    <div>
      <strong>Allergies</strong>
      {rows.map((r, i) => (
        <div className="row" key={i} style={{ marginTop: 8 }}>
          <input placeholder="Allergen" value={r.allergen || ""} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, allergen: e.target.value } : x)))} />
          <input placeholder="Reaction" value={r.reaction || ""} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, reaction: e.target.value } : x)))} />
        </div>
      ))}
      <button className="btn" style={{ marginTop: 8 }} onClick={() => onChange([...rows, { allergen: "", reaction: "", severity: "moderate" }])}>
        Add allergy
      </button>
    </div>
  );
}
