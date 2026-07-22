import React, { useEffect, useState } from "react";
import { listInvoices } from "../api.js";

const STATUS_TABS = [
  ["all", "All"],
  ["todo", "To review"],
  ["done", "Verified"],
];

/**
 * The review queue: searchable, filterable by status, and paged. Refreshes on
 * an interval so folder-dropped invoices appear, without disturbing the search
 * box or the current page.
 */
export default function Inbox({ onOpen }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, page: 1, pages: 1 });

  // Debounce the search so we don't hit the API on every keystroke.
  const [debouncedQ, setDebouncedQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  // A new search or filter starts back at page 1.
  useEffect(() => setPage(1), [debouncedQ, status]);

  useEffect(() => {
    let alive = true;
    const load = () =>
      listInvoices({ q: debouncedQ, status, page })
        .then((d) => alive && setData(d))
        .catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [debouncedQ, status, page]);

  return (
    <div className="inbox">
      <div className="inbox-head">
        <span>Review queue</span>
        <span className="inbox-count">{data.total}</span>
      </div>

      <div className="inbox-controls">
        <input
          className="inbox-search"
          type="search"
          placeholder="Search supplier, invoice number, amount…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <div className="inbox-tabs">
          {STATUS_TABS.map(([val, label]) => (
            <button
              key={val}
              className={status === val ? "tab active" : "tab"}
              onClick={() => setStatus(val)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {data.items.length === 0 ? (
        <p className="hint">
          {debouncedQ
            ? `No invoices match “${debouncedQ}”.`
            : "Waiting for invoices. Drop a PDF into data/intake/incoming or use Upload above."}
        </p>
      ) : (
        <ul className="inbox-list">
          {data.items.map((it) => (
            <li key={it.id} onClick={() => onOpen(it.id)}>
              <div className="inbox-main">
                <span className="inbox-supplier">{it.supplier || it.filename}</span>
                <span className="inbox-file">{it.filename}</span>
              </div>
              <div className="inbox-meta">
                {it.total && (
                  <span className="inbox-total">
                    {it.total} {it.currency}
                  </span>
                )}
                {it.issues > 0 && (
                  <span className="inbox-issues" title={`${it.issues} check(s) to look at`}>
                    ⚠ {it.issues}
                  </span>
                )}
                {it.handover_status === "delivered" ? (
                  <span className="inbox-badge badge-marathon">→ Marathon</span>
                ) : (
                  <span
                    className={`inbox-badge ${it.verified ? "badge-done" : "badge-todo"}`}
                  >
                    {it.verified ? "verified" : "to review"}
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {data.pages > 1 && (
        <div className="inbox-pager">
          <button disabled={data.page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Prev
          </button>
          <span>
            Page {data.page} of {data.pages}
          </span>
          <button
            disabled={data.page >= data.pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
