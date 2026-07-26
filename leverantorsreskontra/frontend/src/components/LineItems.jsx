import React from "react";

/**
 * Fakturans rader, konterade mot BAS-konto + momskod. En faktura kan delas på
 * flera konton, så varje rad bär sin egen kontering. Raderna är bundna till sin
 * ruta på fakturan, precis som fälten.
 */
export default function LineItems({
  items,
  konton,
  koder,
  activeId,
  onPick,
  onKonto,
  onMomskod,
}) {
  if (!items || items.length === 0) return null;

  const konterad = (it) => it.konto && it.momskod;
  const antalKonterade = items.filter(konterad).length;
  const allaKonterade = antalKonterade === items.length;

  return (
    <div className="lineitems">
      <div className="lineitems-head">
        <span>Rader → konto &amp; moms</span>
        <span className={allaKonterade ? "alloc-ok" : "alloc-todo"}>
          {allaKonterade ? "alla rader konterade" : `${antalKonterade}/${items.length} konterade`}
        </span>
      </div>
      <table>
        <tbody>
          {items.map((it) => {
            const id = `row:${it.index}`;
            return (
              <tr
                key={it.index}
                data-row={id}
                className={`row status-${it.status} ${id === activeId ? "active" : ""}`}
                onClick={() => onPick(id)}
              >
                <td className="desc" title={it.description}>
                  {it.description || <em>(ingen beskrivning)</em>}
                </td>
                <td className="amt">{it.amount}</td>
                <td className="proj">
                  <select
                    value={it.konto || ""}
                    onClick={(e) => e.stopPropagation()}
                    onFocus={() => onPick(id)}
                    onChange={(e) => onKonto(it.index, e.target.value)}
                  >
                    <option value="">— konto —</option>
                    {konton.map((k) => (
                      <option key={k.nummer} value={k.nummer}>
                        {k.nummer} · {k.namn}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="moms">
                  <select
                    value={it.momskod || ""}
                    onClick={(e) => e.stopPropagation()}
                    onFocus={() => onPick(id)}
                    onChange={(e) => onMomskod(it.index, e.target.value)}
                  >
                    <option value="">— moms —</option>
                    {koder.map((m) => (
                      <option key={m.kod} value={m.kod}>
                        {m.kod}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
