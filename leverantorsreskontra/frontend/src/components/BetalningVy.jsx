import React, { useCallback, useEffect, useMemo, useState } from "react";
import { getBetalningUnderlag } from "../api.js";

const komma = (s) => (s ? String(s).replace(".", ",") : "");

function konto(r) {
  if (r.bankgiro) return { typ: "Bankgiro", nr: r.bankgiro };
  if (r.plusgiro) return { typ: "Plusgiro", nr: r.plusgiro };
  if (r.iban) return { typ: "IBAN", nr: r.iban };
  return null;
}
const betalbar = (r) => konto(r) && parseFloat(r.belopp) > 0;

/**
 * Betalning — slutsteget. Välj bland attesterade fakturor med kryssrutor och
 * skapa en betalfil (ISO 20022 pain.001) för urvalet. Poster utan konto kan
 * inte väljas.
 */
export default function BetalningVy() {
  const [rows, setRows] = useState([]);
  // Vi spårar *avvalda* id:n. Allt betalbart är valt som standard; det som
  // användaren kryssar bort läggs här (och nya poster blir automatiskt valda).
  const [avvalda, setAvvalda] = useState(() => new Set());
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    getBetalningUnderlag()
      .then((data) => { setError(null); setRows(data); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const betalbara = useMemo(() => rows.filter(betalbar), [rows]);
  const saknar = rows.length - betalbara.length;
  const valda = useMemo(() => betalbara.filter((r) => !avvalda.has(r.id)), [betalbara, avvalda]);
  const valdaIds = valda.map((r) => r.id);
  const allaValda = betalbara.length > 0 && valda.length === betalbara.length;

  const summor = useMemo(() => {
    const s = {};
    for (const r of valda) {
      const c = (r.currency || "SEK").toUpperCase();
      s[c] = (s[c] || 0) + parseFloat(r.belopp || 0);
    }
    return s;
  }, [valda]);
  const summaStr =
    Object.entries(summor).map(([c, v]) => `${komma(v.toFixed(2))} ${c}`).join(" · ") || "0,00";

  function toggle(id) {
    setAvvalda((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function toggleAlla() {
    setAvvalda(allaValda ? new Set(betalbara.map((r) => r.id)) : new Set());
  }

  const url = `/api/pain/export?ids=${valdaIds.join(",")}`;
  const kanBetala = valda.length > 0;

  return (
    <div className="vy">
      <div className="vy-head">
        <h2>Betalning</h2>
        <span className="vy-count">{rows.length}</span>
      </div>
      <p className="vy-lead">Välj attesterade fakturor och skapa en betalfil för urvalet.
        Poster utan mottagarkonto kan inte betalas.</p>

      {error && <div className="error inline">{error}</div>}

      <div className="betal-panel">
        <div className="betal-sum">
          <div><span className="lbl">Valda</span><b>{valda.length} av {betalbara.length}</b></div>
          <div><span className="lbl">Summa</span><b>{summaStr}</b></div>
          {saknar > 0 && (
            <div className="warn"><span className="lbl">Utan konto</span><b>{saknar} kan ej betalas</b></div>
          )}
        </div>
        <div className="betal-actions">
          <a className={`btn-prim${kanBetala ? "" : " disabled"}`}
             href={kanBetala ? url : undefined} aria-disabled={!kanBetala}>
            Skapa betalfil ({valda.length})
          </a>
          <a className="btn-sec" href="/api/sie/export" title="Bokföringsfil (SIE4)">Exportera SIE</a>
          <a className="btn-sec" href="/api/rapporter/godkanda" target="_blank" rel="noopener">Rapport</a>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="hint">Inga attesterade fakturor att betala. Attestera fakturor först.</p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead><tr>
              <th className="chk"><input type="checkbox" checked={allaValda}
                onChange={toggleAlla} aria-label="Välj alla" /></th>
              <th>Leverantör</th><th>Fakturanr</th><th>Förfaller</th>
              <th className="num">Belopp</th><th>Mottagarkonto</th><th>OCR</th>
            </tr></thead>
            <tbody>
              {rows.map((r) => {
                const k = konto(r);
                const kan = betalbar(r);
                return (
                  <tr key={r.id} className={kan ? (avvalda.has(r.id) ? "" : "vald") : "row-warn"}>
                    <td className="chk">
                      <input type="checkbox" disabled={!kan}
                        checked={kan && !avvalda.has(r.id)}
                        onChange={() => toggle(r.id)} aria-label={`Välj ${r.supplier}`} />
                    </td>
                    <td>{r.supplier || "—"}</td>
                    <td className="mono">{r.invoice_number || "—"}</td>
                    <td>{r.due_date || "—"}</td>
                    <td className="num">{komma(r.belopp)} {r.currency}</td>
                    <td>{k ? <><span className="kt">{k.typ}</span> <span className="mono">{k.nr}</span></>
                          : <span className="saknas">⚠ konto saknas</span>}</td>
                    <td className="mono">{r.payment_reference || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
