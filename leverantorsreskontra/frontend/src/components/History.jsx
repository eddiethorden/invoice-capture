import React, { useEffect, useState } from "react";
import { getAudit } from "../api.js";

const LABEL = {
  ingested: "inläst av systemet",
  field_corrected: "rättade",
  project_assigned: "kodade",
  kontering_satt: "konterade",
  verifikat_byggt: "byggde verifikat",
  verified: "godkände",
  granskad: "granskad – klar för attest",
  attesterad: "attesterade",
  avvisad: "avvisade",
  handover_queued: "köade för överföring",
  handed_over: "överförd",
  handover_failed: "överföring misslyckades",
};

/**
 * The audit trail for the open invoice: what the system proposed, what was
 * changed, by whom and when. Append-only and hash-chained on the server.
 * `refreshKey` bumps after an approve so the trail reloads.
 */
export default function History({ invoiceId, refreshKey }) {
  const [events, setEvents] = useState([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!invoiceId) return;
    getAudit(invoiceId).then(setEvents).catch(() => setEvents([]));
  }, [invoiceId, refreshKey]);

  return (
    <div className="history">
      <button className="history-head" onClick={() => setOpen((v) => !v)}>
        <span>Historik</span>
        <span className="history-count">{events.length}</span>
        <span className="history-caret">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ul className="history-list">
          {events.map((e) => (
            <li key={e.seq} className={`hist hist-${e.action}`}>
              <span className="hist-who">{e.actor}</span>
              <span className="hist-what">
                {LABEL[e.action] || e.action}
                {e.field_key && <span className="hist-key"> {e.field_key}</span>}
                {e.action === "field_corrected" && (
                  <span className="hist-diff">
                    {" "}
                    <s>{e.old_value || "—"}</s> → <b>{e.new_value}</b>
                  </span>
                )}
                {(e.action === "project_assigned" ||
                  e.action === "kontering_satt" ||
                  e.action === "attesterad") && (
                  <span className="hist-diff"> → {e.new_value}</span>
                )}
                {e.note && <span className="hist-note"> {e.note}</span>}
              </span>
              <span className="hist-ts">{e.ts?.replace("T", " ").replace("+00:00", "")}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
