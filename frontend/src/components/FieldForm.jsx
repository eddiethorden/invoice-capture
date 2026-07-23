import React from "react";

const STATUS_LABEL = {
  green: "Read - high confidence",
  amber: "Low confidence - please look",
  red: "Failed a check",
  grey: "Not found on the page",
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
          <button className="approve" onClick={onApprove} disabled={verified}>
            {verified ? "Verified ✓" : "Approve (⌘⏎)"}
          </button>
          {verified && handover && handover.status !== "none" && (
            <div className={`handover handover-${handover.status}`}>
              {handover.status === "delivered" ? (
                <>Delivered to {handoverLabel} · <b>{handover.marathon_ref}</b></>
              ) : handover.status === "failed" ? (
                <>{handoverLabel} handover failed</>
              ) : (
                <>Handing over to {handoverLabel}…</>
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
                  ? "not found"
                  : `${Math.round(f.confidence * 100)}%`}
              </span>
            </span>
            <input
              type="text"
              value={f.value}
              placeholder={f.status === "grey" ? "not found - type or click the page" : ""}
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
