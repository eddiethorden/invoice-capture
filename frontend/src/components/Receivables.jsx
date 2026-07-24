import React, { useEffect, useState } from "react";
import { listReceivables } from "../api.js";

/**
 * Receivables (money owed to us), read from the Accounts Receivable module.
 * Refreshes on an interval so newly billed customer invoices appear. Read-only —
 * this system captures supplier invoices (payables); receivables are fed by a
 * separate billing producer.
 */
export default function Receivables() {
  const [rows, setRows] = useState([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    const load = () =>
      listReceivables()
        .then((d) => {
          if (!alive) return;
          setRows(d);
          setFailed(false);
        })
        .catch(() => alive && setFailed(true));
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const overdue = rows.filter((r) => r.status === "overdue").length;
  const open = rows.length - overdue;

  return (
    <div className="inbox">
      <div className="inbox-head">
        <span>Receivables</span>
        <span className="inbox-count">{rows.length}</span>
      </div>

      {rows.length > 0 && (
        <div className="recv-stats">
          <span>{open} open</span>
          <span>{overdue} overdue</span>
        </div>
      )}

      {failed ? (
        <p className="hint">
          Couldn’t reach the Accounts Receivable module. Is it running on :8020?
        </p>
      ) : rows.length === 0 ? (
        <p className="hint">
          No receivables yet. A billing producer posts customer invoices to the AR
          module’s intake API.
        </p>
      ) : (
        <ul className="inbox-list">
          {rows.map((r) => (
            <li key={r.id} className="recv-row">
              <div className="inbox-main">
                <span className="inbox-supplier">{r.customer || "—"}</span>
                <span className="inbox-file">
                  {r.reference}
                  {r.invoice_number ? ` · ${r.invoice_number}` : ""}
                </span>
              </div>
              <div className="inbox-meta">
                {r.total && (
                  <span className="inbox-total">
                    {r.total} {r.currency}
                  </span>
                )}
                {r.due_date && <span className="recv-due">due {r.due_date}</span>}
                <span className={`inbox-badge badge-${r.status}`}>{r.status}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
