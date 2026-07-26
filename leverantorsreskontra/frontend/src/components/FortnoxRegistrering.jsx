import React, { useMemo } from "react";
import InvoiceViewer from "./InvoiceViewer.jsx";

// Verktygsrad (visuell, som i Fortnox).
const TOOLBAR = [
  "Kommentar", "Kreditupplysning", "Inaktivera betalfil",
  "Utbetalningar", "Kopiera", "Skapa kreditfaktura",
];

// Fortnox-fält -> vårt extraktionsfält (null = lokalt/visuellt fält).
const FORM = [
  ["Leverantör", "supplier_name"],
  ["Fakturadatum", "invoice_date"],
  ["Förfallodatum", "due_date"],
  ["Total", "total_amount"],
  ["Moms", "vat_amount"],
  ["OCR", "payment_reference"],
  ["Fakturanummer", "invoice_number"],
  ["Valuta", "currency"],
  ["Kurs", null, "1,0000"],
  ["Enhet", null, ""],
  ["Kostnadsställe", null, ""],
  ["Vår referens", null, ""],
  ["Leverantörens referens", "po_reference"],
  ["Konteringsmall", null, ""],
  ["Bankgiro", "bankgiro"],
  ["Plusgiro", "plusgiro"],
];

// Belopp från verifikatet ("800.00") visas med svensk decimalkomma.
const komma = (s) => (s ? String(s).replace(".", ",") : "");

/**
 * Fortnox-liknande registrering av leverantörsfaktura: fakturabilden till
 * vänster (tolkas automatiskt, avlästa värden som rutor), registreringsformulär
 * och kontering till höger — förifyllt från extraktionen och verifikatet.
 */
export default function FortnoxRegistrering({
  invoice, fields, lineItems, verifikat, boxes, activeKey, onPick, onChange,
}) {
  const byKey = useMemo(
    () => Object.fromEntries(fields.map((f) => [f.key, f])),
    [fields]
  );

  const momstyp = lineItems.some((li) => (li.momskod || "").startsWith("RC"))
    ? "Omv. Skattsk."
    : "Normal";

  const rader = verifikat?.rader?.length
    ? verifikat.rader
    : [{ konto: "2440", kontonamn: "Leverantörsskulder", debet: "0", kredit: "0", text: "" }];

  const sumD = verifikat?.summa_debet || "0.00";
  const sumK = verifikat?.summa_kredit || "0.00";
  const diff = (parseFloat(sumD) - parseFloat(sumK)).toFixed(2);

  return (
    <div className="fnx">
      <div className="fnx-bar">
        <div className="fnx-titles">
          <span className="fnx-doc">LEVERANTÖRSFAKTURA <span className="fnx-star">6*</span></span>
          <span className="fnx-vernr">VER.NR: —</span>
        </div>
        <div className="fnx-tools">
          {TOOLBAR.map((t) => (
            <button key={t} disabled>{t}</button>
          ))}
        </div>
      </div>

      <div className="fnx-split">
        <div className="fnx-left">
          <InvoiceViewer invoice={invoice} boxes={boxes} activeId={activeKey} onPick={onPick} />
        </div>

        <div className="fnx-right">
          <div className="fnx-form">
            {FORM.map(([label, key, def]) => {
              const f = key ? byKey[key] : null;
              const val = key ? (f?.value ?? "") : def;
              const active = key && key === activeKey;
              return (
                <label key={label} className={`fnx-field${active ? " active" : ""}`}>
                  <span className="fnx-label">{label}</span>
                  <input
                    value={val}
                    readOnly={!key}
                    onFocus={() => key && onPick(key)}
                    onChange={(e) => key && onChange(key, e.target.value)}
                  />
                </label>
              );
            })}
            <div className="fnx-field fnx-momstyp">
              <span className="fnx-label">Momstyp</span>
              <div className="fnx-radios">
                {["Normal", "EU", "Omv. Skattsk."].map((m) => (
                  <label key={m}>
                    <input type="radio" name="momstyp" checked={momstyp === m} readOnly /> {m}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <div className="fnx-note">
            Tidigare kontering tas fram utifrån hur ni bokfört den senaste fakturan
            från leverantören.
          </div>

          <div className="fnx-kont">
            <div className="fnx-tabs">
              <button className="active">Kontoregistrering</button>
              <button disabled>Artikelregistrering</button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>KONTO</th><th>KS</th><th>KONTOBENÄMNING</th>
                  <th>TRANSAKTIONSINFO</th>
                  <th className="num">DEBET</th><th className="num">KREDIT</th>
                </tr>
              </thead>
              <tbody>
                {rader.map((r, i) => (
                  <tr key={i}>
                    <td className="k">{r.konto}</td>
                    <td></td>
                    <td>{r.kontonamn}</td>
                    <td>{r.text || ""}</td>
                    <td className="num">{r.debet !== "0" ? komma(r.debet) : ""}</td>
                    <td className="num">{r.kredit !== "0" ? komma(r.kredit) : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="sum">
                  <td colSpan="4">Summa</td>
                  <td className="num">{komma(sumD)}</td>
                  <td className="num">{komma(sumK)}</td>
                </tr>
                <tr className="diff">
                  <td colSpan="4">Differens</td>
                  <td></td>
                  <td className="num">{komma(diff)}</td>
                </tr>
              </tfoot>
            </table>
            <div className="fnx-extra">
              <label>Öresutjämning <input readOnly value="" /></label>
              <label>Frakt <input readOnly value="" /></label>
              <label>Fakturaavgift <input readOnly value="" /></label>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
