import React, { useState } from "react";

const ETIKETT = {
  utkast: "Utkast",
  granskad: "Granskad — väntar på attest",
  attesterad: "Attesterad",
  avvisad: "Avvisad",
};

/**
 * Attestflöde: en granskare kodar och granskar (verify), en annan attestant
 * attesterar (fyra ögon). Först attesterade fakturor kan bokföras/betalas.
 */
export default function Attest({ invoice, onAttestera, onAvvisa }) {
  const status = invoice.attest_status || "utkast";
  const [attestant, setAttestant] = useState("");
  const [kommentar, setKommentar] = useState("");

  return (
    <div className="attest">
      <div className="attest-head">
        <span>Attest</span>
        <span className={`attest-badge attest-${status}`}>{ETIKETT[status] || status}</span>
      </div>

      {invoice.granskare && (
        <div className="attest-meta">
          Granskad av <b>{invoice.granskare}</b>
          {invoice.granskad_at ? ` · ${invoice.granskad_at}` : ""}
        </div>
      )}
      {status === "attesterad" && (
        <div className="attest-meta ok">
          Attesterad av <b>{invoice.attestant}</b>
          {invoice.attesterad_at ? ` · ${invoice.attesterad_at}` : ""}
        </div>
      )}
      {status === "avvisad" && (
        <div className="attest-meta fel">
          Avvisad{invoice.attest_kommentar ? ` · ${invoice.attest_kommentar}` : ""} — koda
          om och godkänn igen.
        </div>
      )}

      {status === "granskad" && (
        <div className="attest-actions">
          <input
            className="attest-input"
            placeholder="Attestant (annan än granskaren)"
            value={attestant}
            onChange={(e) => setAttestant(e.target.value)}
          />
          <button
            className="attest-btn"
            disabled={!attestant.trim()}
            onClick={() => onAttestera(attestant.trim())}
          >
            Attestera
          </button>
          <input
            className="attest-input"
            placeholder="Kommentar (vid avvisning)"
            value={kommentar}
            onChange={(e) => setKommentar(e.target.value)}
          />
          <button className="attest-btn ghost-btn" onClick={() => onAvvisa(kommentar.trim())}>
            Avvisa
          </button>
        </div>
      )}

      {status === "utkast" && (
        <div className="attest-meta">Godkänn (⌘/Ctrl+Enter) för att skicka till attest.</div>
      )}
    </div>
  );
}
