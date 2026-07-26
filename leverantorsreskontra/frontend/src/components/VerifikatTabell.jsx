import React from "react";

/**
 * Presentational: renders a verifikat (from /api/kontering/forslag or a stored
 * invoice.verifikat) as a debet/kredit table with sums, a balance badge, and
 * the diff vs the invoice's stated brutto. Shared by the Kontering tab and the
 * verification screen.
 */
export default function VerifikatTabell({ verifikat }) {
  if (!verifikat) return null;
  const { rader, summa_debet, summa_kredit, balanserar, differens_mot_angivet_total } =
    verifikat;
  return (
    <>
      <table className="kont-table verifikat">
        <thead>
          <tr>
            <th>Konto</th>
            <th className="kont-num">Debet</th>
            <th className="kont-num">Kredit</th>
          </tr>
        </thead>
        <tbody>
          {rader.map((r, i) => (
            <tr key={i}>
              <td>
                <span className="v-konto">{r.konto}</span> {r.kontonamn}
                {r.text ? <span className="v-text"> · {r.text}</span> : ""}
              </td>
              <td className="kont-num">{r.debet !== "0" ? r.debet : ""}</td>
              <td className="kont-num">{r.kredit !== "0" ? r.kredit : ""}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Summa</td>
            <td className="kont-num">{summa_debet}</td>
            <td className="kont-num">{summa_kredit}</td>
          </tr>
        </tfoot>
      </table>
      <div className="kont-status">
        <span className={balanserar ? "balans ok" : "balans fel"}>
          {balanserar ? "✓ Balanserar" : "✗ Balanserar inte"}
        </span>
        {differens_mot_angivet_total != null && differens_mot_angivet_total !== "0" && (
          <span className="diff" title="Leverantörsskuld minus angiven bruttototal">
            Diff mot total: {differens_mot_angivet_total}
          </span>
        )}
      </div>
    </>
  );
}
