import { useEffect, useState } from "react";

export type ToastDetail = { title: string; body?: string; kind?: "ok" | "error" };

export function notify(title: string, body = "") {
  window.dispatchEvent(new CustomEvent<ToastDetail>("sbar:toast", { detail: { title, body, kind: "ok" } }));
}

export function notifyError(title: string, body = "") {
  window.dispatchEvent(new CustomEvent<ToastDetail>("sbar:toast", { detail: { title, body, kind: "error" } }));
}

export function ToastHost() {
  const [toast, setToast] = useState<ToastDetail | null>(null);

  useEffect(() => {
    function onToast(e: Event) {
      const detail = (e as CustomEvent<ToastDetail>).detail;
      if (!detail?.title) return;
      setToast(detail);
    }
    window.addEventListener("sbar:toast", onToast);
    return () => window.removeEventListener("sbar:toast", onToast);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(t);
  }, [toast]);

  if (!toast) return null;
  return (
    <div className={"toast" + (toast.kind === "error" ? " error" : "")} role="status">
      <strong>{toast.title}</strong>
      {toast.body ? <p>{toast.body}</p> : null}
    </div>
  );
}
