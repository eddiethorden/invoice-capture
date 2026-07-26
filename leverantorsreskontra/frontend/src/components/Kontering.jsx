import React, { useEffect, useMemo, useState } from "react";
import { getKonton, getMomskoder, konteringForslag } from "../api.js";
import VerifikatTabell from "./VerifikatTabell.jsx";

const TOM_RAD = { beskrivning: "", netto: "", konto: "", momskod: "SE25" };

/**
 * Konteringsvy — koda varje fakturarad mot ett BAS-konto och en momskod, och se
 * det balanserade verifikatet uppdateras live. Milstolpe 1 (BAS + moms).
 */
export default function Kontering() {
  const [konton, setKonton] = useState([]);
  const [koder, setKoder] = useState([]);
  const [rader, setRader] = useState([{ ...TOM_RAD }]);
  const [angivetTotal, setAngivetTotal] = useState("");
  const [verifikat, setVerifikat] = useState(null);
  const [fel, setFel] = useState(null);

  useEffect(() => {
    getKonton()
      .then((k) => {
        setKonton(k);
        // Default the first row's account once accounts load.
        setRader((prev) =>
          prev.map((r, i) => (i === 0 && !r.konto ? { ...r, konto: k[0]?.nummer || "" } : r))
        );
      })
      .catch(() => setFel("Kunde inte hämta kontoplan (kör backend på :8000?)"));
    getMomskoder().then(setKoder).catch(() => {});
  }, []);

  // Rader som är fullständiga nog att kontera (konto + ett nettobelopp).
  const kompletta = useMemo(
    () => rader.filter((r) => r.konto && String(r.netto).trim() !== ""),
    [rader]
  );

  // Bygg verifikatet på servern när kompletta rader eller totalen ändras (debounce).
  useEffect(() => {
    if (kompletta.length === 0) {
      setVerifikat(null);
      setFel(null);
      return;
    }
    const t = setTimeout(() => {
      konteringForslag(kompletta, angivetTotal)
        .then((v) => {
          setVerifikat(v);
          setFel(null);
        })
        .catch((e) => {
          setVerifikat(null);
          setFel(e.message);
        });
    }, 300);
    return () => clearTimeout(t);
  }, [kompletta, angivetTotal]);

  function uppdatera(i, fält, värde) {
    setRader((prev) => prev.map((r, idx) => (idx === i ? { ...r, [fält]: värde } : r)));
  }
  function läggTill() {
    setRader((prev) => [...prev, { ...TOM_RAD, konto: konton[0]?.nummer || "" }]);
  }
  function taBort(i) {
    setRader((prev) => (prev.length > 1 ? prev.filter((_, idx) => idx !== i) : prev));
  }

  return (
    <div className="kontering">
      <div className="inbox-head">
        <span>Kontering</span>
        <span className="inbox-count">{kompletta.length} rader</span>
      </div>

      <div className="kont-grid">
        {/* Konteringsrader */}
        <section className="kont-rader">
          <table className="kont-table">
            <thead>
              <tr>
                <th>Beskrivning</th>
                <th>Konto</th>
                <th>Momskod</th>
                <th className="kont-num">Netto</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rader.map((r, i) => (
                <tr key={i}>
                  <td>
                    <input
                      value={r.beskrivning}
                      placeholder="t.ex. Kontorsmateriel"
                      onChange={(e) => uppdatera(i, "beskrivning", e.target.value)}
                    />
                  </td>
                  <td>
                    <select value={r.konto} onChange={(e) => uppdatera(i, "konto", e.target.value)}>
                      <option value="">— välj konto —</option>
                      {konton.map((k) => (
                        <option key={k.nummer} value={k.nummer}>
                          {k.nummer} {k.namn}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select value={r.momskod} onChange={(e) => uppdatera(i, "momskod", e.target.value)}>
                      {koder.map((m) => (
                        <option key={m.kod} value={m.kod}>
                          {m.kod} · {m.beskrivning}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="kont-num">
                    <input
                      className="kont-belopp"
                      value={r.netto}
                      inputMode="decimal"
                      placeholder="0,00"
                      onChange={(e) => uppdatera(i, "netto", e.target.value)}
                    />
                  </td>
                  <td>
                    <button className="kont-remove" title="Ta bort rad" onClick={() => taBort(i)}>
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="kont-actions">
            <button className="ghost" onClick={läggTill}>
              + Lägg till rad
            </button>
            <label className="kont-total">
              Fakturans total (brutto)
              <input
                value={angivetTotal}
                inputMode="decimal"
                placeholder="valfritt"
                onChange={(e) => setAngivetTotal(e.target.value)}
              />
            </label>
          </div>
        </section>

        {/* Verifikat */}
        <section className="kont-verifikat">
          <h3>Verifikat</h3>
          {fel && <div className="kont-fel">{fel}</div>}
          {!verifikat && !fel && <p className="hint">Koda minst en rad för att se verifikatet.</p>}
          {verifikat && <VerifikatTabell verifikat={verifikat} />}
        </section>
      </div>
    </div>
  );
}
