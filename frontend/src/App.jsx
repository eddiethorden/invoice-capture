import React, { useCallback, useEffect, useRef, useState } from "react";
import InvoiceViewer from "./components/InvoiceViewer.jsx";
import FieldForm from "./components/FieldForm.jsx";
import { uploadInvoice, verifyInvoice } from "./api.js";

export default function App() {
  const [invoice, setInvoice] = useState(null);
  const [fields, setFields] = useState([]);
  const [activeKey, setActiveKey] = useState(null);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const loadInvoice = useCallback((data) => {
    setInvoice(data);
    setFields(data.fields);
    setVerified(Boolean(data.verified));
    // Land the reviewer on the first thing that needs attention.
    const firstProblem = data.fields.find(
      (f) => f.status === "red" || f.status === "amber" || f.status === "grey"
    );
    setActiveKey((firstProblem || data.fields[0])?.key ?? null);
  }, []);

  async function onFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      loadInvoice(await uploadInvoice(file));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const onChange = useCallback((key, value) => {
    setFields((prev) =>
      prev.map((f) =>
        f.key === key ? { ...f, value, status: f.status === "grey" ? "green" : f.status } : f
      )
    );
  }, []);

  const onAdvance = useCallback(
    (index) => {
      const next = fields[index + 1];
      if (next) {
        setActiveKey(next.key);
        document
          .querySelectorAll(".field-row input")
          [index + 1]?.focus();
      }
    },
    [fields]
  );

  const onApprove = useCallback(async () => {
    if (!invoice) return;
    try {
      await verifyInvoice(invoice.id, fields);
      setVerified(true);
    } catch (err) {
      setError(err.message);
    }
  }, [invoice, fields]);

  // Cmd/Ctrl+Enter approves the whole document.
  useEffect(() => {
    function onKey(e) {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        onApprove();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onApprove]);

  // When the active field changes, scroll its box into view on the left.
  useEffect(() => {
    if (!activeKey) return;
    document
      .querySelector(`rect[data-box="${activeKey}"]`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeKey]);

  // Clicking a box focuses the matching form field.
  const onPick = useCallback((key) => {
    setActiveKey(key);
    const idx = fields.findIndex((f) => f.key === key);
    document.querySelectorAll(".field-row input")[idx]?.focus();
  }, [fields]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Automated Invoice Capture</div>
        <div className="intake">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            onChange={onFile}
            hidden
          />
          <button onClick={() => fileRef.current?.click()} disabled={busy}>
            {busy ? "Reading…" : "Upload invoice (PDF)"}
          </button>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      {!invoice && !busy && (
        <div className="empty">
          <p>Upload a supplier invoice to begin.</p>
          <p className="hint">
            The software proposes; a person verifies. Every value it reads is
            drawn on the invoice for you to confirm or correct.
          </p>
        </div>
      )}

      {invoice && (
        <main className="split">
          <InvoiceViewer
            invoice={invoice}
            fields={fields}
            activeKey={activeKey}
            onPick={onPick}
          />
          <FieldForm
            invoice={invoice}
            fields={fields}
            activeKey={activeKey}
            onFocusField={setActiveKey}
            onChange={onChange}
            onAdvance={onAdvance}
            onApprove={onApprove}
            checks={invoice.checks}
            signals={invoice.signals}
            verified={verified}
          />
        </main>
      )}
    </div>
  );
}
