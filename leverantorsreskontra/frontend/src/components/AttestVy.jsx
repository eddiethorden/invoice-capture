import React, { useCallback, useEffect, useState } from "react";
import { getAttestKo, attesteraInvoice, avvisaInvoice } from "../api.js";

const komma = (s) => (s ? String(s).replace(".", ",") : "");

/**
 * Attestkö — granskade fakturor som väntar på attest. En attestant (annan än
 * granskaren, fyra ögon) attesterar; först då kan fakturan bokföras och betalas.
 */
export default function AttestVy() {
  const [rows, setRows] = useState([]);
  const [attestant, setAttestant] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);

  const load = useCallback(
    () => getAttestKo().then((r) => { setRows(r); setError(null); }).catch((e) => setError(e.message)),
    []
  );
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  async function attest(id) {
    if (!attestant.trim()) return;
    setBusy(id);
    try { await attesteraInvoice(id, attestant.trim()); await load(); }
    catch (e) { setError(e.message); }
    finally { setBusy(null); }
  }
  async function avvisa(id) {
    const kommentar = window.prompt("Kommentar (skäl till avvisning):") ?? null;
    if (kommentar === null) return;
    setBusy(id);
    try { await avvisaInvoice(id, kommentar); await load(); }
    catch (e) { setError(e.message); }
    finally { setBusy(null); }
  }

  return (
    <div className="vy">
      <div className="vy-head">
        <h2>Attest</h2>
        <span className="vy-count">{rows.length}</span>
        <label className="attestant-fld">
          Attestant
          <input value={attestant} placeholder="ditt namn (≠ granskaren)"
            onChange={(e) => setAttestant(e.target.value)} />
        </label>
      </div>
      <p className="vy-lead">Granskade fakturor som väntar på attest. Fyra ögon krävs —
        attestanten måste vara en annan person än granskaren.</p>

      {error && <div className="error inline">{error}</div>}

      {rows.length === 0 ? (
        <p className="hint">Inga fakturor väntar på attest.</p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>Leverantör</th><th>Fakturanr</th><th>Förfaller</th>
              <th className="num">Belopp</th><th>Granskare</th><th className="act"></th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.supplier || "—"}</td>
                  <td className="mono">{r.invoice_number || "—"}</td>
                  <td>{r.due_date || "—"}</td>
                  <td className="num">{komma(r.belopp)} {r.currency}</td>
                  <td>{r.granskare || "—"}</td>
                  <td className="act">
                    <button className="btn-ok" disabled={!attestant.trim() || busy === r.id}
                      onClick={() => attest(r.id)}>Attestera</button>
                    <button className="btn-ghost" disabled={busy === r.id}
                      onClick={() => avvisa(r.id)}>Avvisa</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
