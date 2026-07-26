import React, { useEffect, useMemo, useState } from "react";
import { listReceivables } from "../api.js";

// Columns, in display order. `num`/`date` pick the right comparator; the rest
// sort as text. `key` is both the sort field and the row property.
const COLUMNS = [
  { key: "reference", label: "Ref" },
  { key: "customer", label: "Kund" },
  { key: "invoice_number", label: "Fakturanr" },
  { key: "total", label: "Belopp", num: true, align: "right" },
  { key: "due_date", label: "Förfaller", date: true },
  { key: "status", label: "Status" },
  { key: "received_at", label: "Mottagen", date: true },
];

const STATUS_TEXT = { open: "öppen", overdue: "förfallen" };

// Parse a localized amount ("48 750,00", "1.299,25") to a number for sorting.
function parseAmount(s) {
  if (!s) return NaN;
  let t = String(s).replace(/\s/g, "");
  const comma = t.includes(","), dot = t.includes(".");
  if (comma && dot) {
    t = t.lastIndexOf(",") > t.lastIndexOf(".")
      ? t.replace(/\./g, "").replace(",", ".")
      : t.replace(/,/g, "");
  } else if (comma) {
    t = t.replace(",", ".");
  }
  return parseFloat(t.replace(/[^0-9.\-]/g, ""));
}

function compare(a, b, col) {
  const va = a[col.key], vb = b[col.key];
  // Empty values always sort last, regardless of direction.
  if (va == null || va === "") return vb == null || vb === "" ? 0 : 1;
  if (vb == null || vb === "") return -1;
  if (col.num) {
    const na = parseAmount(va), nb = parseAmount(vb);
    return (isNaN(na) ? 0 : na) - (isNaN(nb) ? 0 : nb);
  }
  if (col.date) return String(va) < String(vb) ? -1 : String(va) > String(vb) ? 1 : 0;
  return String(va).localeCompare(String(vb));
}

/**
 * Receivables (money owed to us), read from the Accounts Receivable module.
 * Sortable on every column and scrollable with a sticky header. Read-only —
 * this system captures supplier invoices (payables); receivables are fed by a
 * separate billing producer.
 */
export default function Receivables() {
  const [rows, setRows] = useState([]);
  const [failed, setFailed] = useState(false);
  const [sortKey, setSortKey] = useState("received_at");
  const [dir, setDir] = useState("desc"); // matches the module's default order

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

  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === sortKey) || COLUMNS[0];
    const out = [...rows].sort((a, b) => compare(a, b, col));
    if (dir === "desc") out.reverse();
    return out;
  }, [rows, sortKey, dir]);

  function onSort(key) {
    if (key === sortKey) {
      setDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setDir("asc");
    }
  }

  const overdue = rows.filter((r) => r.status === "overdue").length;
  const open = rows.length - overdue;

  return (
    <div className="inbox">
      <div className="inbox-head">
        <span>Kundfordringar</span>
        <span className="inbox-count">{rows.length}</span>
      </div>

      {rows.length > 0 && (
        <div className="recv-stats">
          <span>{open} öppna</span>
          <span>{overdue} förfallna</span>
        </div>
      )}

      {failed ? (
        <p className="hint">
          Kunde inte nå kundreskontramodulen. Körs den på :8020?
        </p>
      ) : rows.length === 0 ? (
        <p className="hint">
          Inga kundfordringar än. En faktureringskälla postar kundfakturor till
          kundreskontrans intake-API.
        </p>
      ) : (
        <div className="recv-scroll">
          <table className="recv-table">
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th
                    key={c.key}
                    className={
                      (c.align === "right" ? "recv-num " : "") +
                      (c.key === sortKey ? "sorted" : "")
                    }
                    onClick={() => onSort(c.key)}
                    title="Klicka för att sortera"
                  >
                    {c.label}
                    <span className="recv-caret">
                      {c.key === sortKey ? (dir === "asc" ? " ▲" : " ▼") : ""}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id}>
                  <td className="recv-ref">{r.reference}</td>
                  <td>{r.customer || "—"}</td>
                  <td>{r.invoice_number || "—"}</td>
                  <td className="recv-num">
                    {r.total ? `${r.total} ${r.currency || ""}` : "—"}
                  </td>
                  <td>{r.due_date || "—"}</td>
                  <td>
                    <span className={`inbox-badge badge-${r.status}`}>
                      {STATUS_TEXT[r.status] || r.status}
                    </span>
                  </td>
                  <td className="recv-received">{r.received_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
