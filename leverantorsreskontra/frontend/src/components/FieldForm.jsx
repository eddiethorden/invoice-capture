import React from "react";

const STATUS_LABEL = {
  green: "Avläst – hög säkerhet",
  amber: "Låg säkerhet – kontrollera",
  red: "Underkänd kontroll",
  grey: "Hittades inte på sidan",
};

/**
 * The right half: the extracted fields as an editable form, permanently
 * linked to the boxes on the left. Fully keyboard-operable - Tab walks the
 * fields in reading order, Enter confirms and advances.
 */
export default function FieldForm({
  invoice,
  fields,
  activeKey,
  onFocusField,
  onChange,
  onAdvance,
  onApprove,
  konteringKlar = true,
  checks,
  signals = [],
  verified,
  handover,
  handoverLabel = "Marathon",
}) {
  const LEVEL_ICON = { ok: "✓", warn: "!", error: "✕" };
  return (
    <div className="form">
      <div className="form-header">
        <div>
          <div className="filename">{invoice.filename}</div>
          <div
            className={`check ${checks.arithmetic_ok === false ? "check-bad" : "check-ok"}`}
          >
            {checks.message}
          </div>
        </div>
        <div className="approve-col">
          <button className={verified ? "approve verified" : "approve"} onClick={onApprove}
            disabled={verified || !konteringKlar}
            title={!konteringKlar ? "Kontera alla rader (konto + momskod) först" : undefined}>
            {verified ? "Granskad ✓" : "Godkänn (⌘⏎)"}
          </button>
          {!verified && !konteringKlar && (
            <div className="approve-hint">Kontera alla rader för att godkänna</div>
          )}
          {verified && handover && handover.status !== "none" && (
            <div className={`handover handover-${handover.status}`}>
              {handover.status === "delivered" ? (
                <>Levererad till {handoverLabel} · <b>{handover.marathon_ref}</b></>
              ) : handover.status === "failed" ? (
                <>Överföring till {handoverLabel} misslyckades</>
              ) : (
                <>Överför till {handoverLabel}…</>
              )}
            </div>
          )}
        </div>
      </div>

      {signals.length > 0 && (
        <ul className="signals">
          {signals.map((s, i) => (
            <li key={i} className={`signal signal-${s.level}`}>
              <span className="signal-icon">{LEVEL_ICON[s.level]}</span>
              {s.message}
            </li>
          ))}
        </ul>
      )}

      <div className="field-list">
        {fields.map((f, i) => (
          <label
            key={f.key}
            className={`field-row status-${f.status} ${
              f.key === activeKey ? "active" : ""
            }`}
          >
            <span className="field-label">
              {f.label}
              <span className="field-status" title={STATUS_LABEL[f.status]}>
                {f.status === "grey"
                  ? "hittas ej"
                  : `${Math.round(f.confidence * 100)}%`}
              </span>
            </span>
            <input
              type="text"
              value={f.value}
              placeholder={f.status === "grey" ? "hittas ej – skriv eller klicka på sidan" : ""}
              onFocus={() => onFocusField(f.key)}
              onChange={(e) => onChange(f.key, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  onAdvance(i);
                }
              }}
            />
          </label>
        ))}
      </div>
    </div>
  );
}
