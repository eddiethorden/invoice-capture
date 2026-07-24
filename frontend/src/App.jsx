import React, { useCallback, useEffect, useRef, useState } from "react";
import InvoiceViewer from "./components/InvoiceViewer.jsx";
import FieldForm from "./components/FieldForm.jsx";
import LineItems from "./components/LineItems.jsx";
import History from "./components/History.jsx";
import Inbox from "./components/Inbox.jsx";
import Receivables from "./components/Receivables.jsx";
import {
  uploadInvoice,
  verifyInvoice,
  getProjects,
  getInvoice,
  getHandover,
  getConfig,
} from "./api.js";

export default function App() {
  const [invoice, setInvoice] = useState(null);
  const [fields, setFields] = useState([]);
  const [lineItems, setLineItems] = useState([]);
  const [projects, setProjects] = useState([]);
  const [handoverLabel, setHandoverLabel] = useState("Marathon");
  const [view, setView] = useState("invoices"); // "invoices" | "receivables"
  const [activeKey, setActiveKey] = useState(null);
  const [verified, setVerified] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const [handover, setHandover] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    getProjects().then(setProjects).catch(() => setProjects([]));
    getConfig().then((c) => setHandoverLabel(c.handover_label)).catch(() => {});
  }, []);

  const openInvoice = useCallback(
    async (id) => {
      setBusy(true);
      setError(null);
      try {
        loadInvoice(await getInvoice(id));
      } catch (err) {
        setError(err.message);
      } finally {
        setBusy(false);
      }
    },
    [] // loadInvoice is stable (defined below with useCallback)
  );

  const loadInvoice = useCallback((data) => {
    setInvoice(data);
    setFields(data.fields);
    setLineItems(data.line_items || []);
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

  const onProject = useCallback((index, code) => {
    setLineItems((prev) =>
      prev.map((it) => (it.index === index ? { ...it, project: code } : it))
    );
  }, []);

  const onApprove = useCallback(async () => {
    if (!invoice) return;
    try {
      await verifyInvoice(invoice.id, fields, lineItems);
      setVerified(true);
      setHistoryKey((k) => k + 1); // reload the audit trail
    } catch (err) {
      setError(err.message);
    }
  }, [invoice, fields, lineItems]);

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

  // Once an invoice is verified, poll its Marathon handover until it settles.
  useEffect(() => {
    if (!invoice || !verified) {
      setHandover(null);
      return;
    }
    let alive = true;
    let timer;
    const poll = async () => {
      try {
        const h = await getHandover(invoice.id);
        if (!alive) return;
        setHandover(h);
        if (h.status === "delivered" || h.status === "failed") return; // settled
      } catch {
        /* keep polling */
      }
      if (alive) timer = setTimeout(poll, 2000);
    };
    poll();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [invoice, verified]);

  // When the active field changes, scroll its box into view on the left.
  useEffect(() => {
    if (!activeKey) return;
    document
      .querySelector(`rect[data-box="${activeKey}"]`)
      ?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeKey]);

  // Clicking a box selects the matching control on the right.
  const onPick = useCallback(
    (id) => {
      setActiveKey(id);
      if (id.startsWith("row:")) {
        document
          .querySelector(`tr.row[data-row="${id}"]`)
          ?.scrollIntoView({ block: "nearest" });
        return;
      }
      const idx = fields.findIndex((f) => f.key === id);
      document.querySelectorAll(".field-row input")[idx]?.focus();
    },
    [fields]
  );

  // Boxes the overlay draws: header fields plus line-item rows.
  const boxes = [
    ...fields
      .filter((f) => f.box)
      .map((f) => ({ id: f.key, page: f.page, status: f.status, box: f.box })),
    ...lineItems
      .filter((li) => li.box)
      .map((li) => ({
        id: `row:${li.index}`,
        page: li.page,
        status: li.status,
        box: li.box,
      })),
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">Automated Invoice Capture</div>
        <nav className="topnav">
          <button
            className={view === "invoices" ? "active" : ""}
            onClick={() => setView("invoices")}
          >
            Invoices
          </button>
          <button
            className={view === "receivables" ? "active" : ""}
            onClick={() => setView("receivables")}
          >
            Receivables
          </button>
        </nav>
        {view === "invoices" && (
          <div className="intake">
            {invoice && (
              <button className="ghost" onClick={() => setInvoice(null)}>
                ← Inbox
              </button>
            )}
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
        )}
      </header>

      {error && <div className="error">{error}</div>}

      {view === "receivables" && <Receivables />}

      {view === "invoices" && !invoice && !busy && (
        <Inbox onOpen={openInvoice} handoverLabel={handoverLabel} />
      )}

      {view === "invoices" && invoice && (
        <main className="split">
          <InvoiceViewer
            invoice={invoice}
            boxes={boxes}
            activeId={activeKey}
            onPick={onPick}
          />
          <div className="rightpanel">
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
              handover={handover}
              handoverLabel={handoverLabel}
            />
            <LineItems
              items={lineItems}
              projects={projects}
              activeId={activeKey}
              onPick={onPick}
              onProject={onProject}
            />
            <History invoiceId={invoice.id} refreshKey={historyKey} />
          </div>
        </main>
      )}
    </div>
  );
}
