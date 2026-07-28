import React, { useCallback, useEffect, useMemo, useState } from "react";
import { getBetalningUnderlag } from "../api.js";

const komma = (s) => (s ? String(s).replace(".", ",") : "");

function konto(r) {
  if (r.bankgiro) return { typ: "Bankgiro", nr: r.bankgiro };
  if (r.plusgiro) return { typ: "Plusgiro", nr: r.plusgiro };
  if (r.iban) return { typ: "IBAN", nr: r.iban };
  return null;
}

/**
 * Betalning — slutsteget. Attesterade fakturor med mottagarkonto samlas till en
 * betalfil (ISO 20022 pain.001). Poster utan konto hoppas över.
 */
export default function BetalningVy() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(
    () => getBetalningUnderlag().then((r) => { setRows(r); setError(null); }).catch((e) => setError(e.message)),
    []
  );
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const { betalbara, saknar, summor } = useMemo(() => {
    const betalbara = rows.filter((r) => konto(r) && parseFloat(r.belopp) > 0);
    const saknar = rows.length - betalbara.length;
    const summor = {};
    for (const r of betalbara) {
      const c = (r.currency || "SEK").toUpperCase();
      summor[c] = (summor[c] || 0) + parseFloat(r.belopp || 0);
    }
    return { betalbara, saknar, summor };
  }, [rows]);

  const summaStr =
    Object.entries(summor).map(([c, v]) => `${komma(v.toFixed(2))} ${c}`).join(" · ") || "0,00";

  return (
    <div className="vy">
      <div className="vy-head">
        <h2>Betalning</h2>
        <span className="vy-count">{rows.length}</span>
      </div>
      <p className="vy-lead">Attesterade fakturor redo att betalas. Skapa betalfilen och
        skicka den till banken.</p>

      {error && <div className="error inline">{error}</div>}

      <div className="betal-panel">
        <div className="betal-sum">
          <div><span className="lbl">Att betala</span><b>{betalbara.length} fakturor</b></div>
          <div><span className="lbl">Summa</span><b>{summaStr}</b></div>
          {saknar > 0 && (
            <div className="warn"><span className="lbl">Utan konto</span><b>{saknar} hoppas över</b></div>
          )}
        </div>
        <div className="betal-actions">
          <a className={`btn-prim${betalbara.length ? "" : " disabled"}`}
             href={betalbara.length ? "/api/pain/export" : undefined}
             aria-disabled={!betalbara.length}>Skapa betalfil (pain.001)</a>
          <a className="btn-sec" href="/api/sie/export" title="Bokföringsfil (SIE4)">Exportera SIE</a>
          <a className="btn-sec" href="/api/rapporter/godkanda" target="_blank" rel="noopener">Rapport</a>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="hint">Inga attesterade fakturor att betala. Attestera fakturor först.</p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>Leverantör</th><th>Fakturanr</th><th>Förfaller</th>
              <th className="num">Belopp</th><th>Mottagarkonto</th><th>OCR</th></tr></thead>
            <tbody>
              {rows.map((r) => {
                const k = konto(r);
                return (
                  <tr key={r.id} className={k ? "" : "row-warn"}>
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
