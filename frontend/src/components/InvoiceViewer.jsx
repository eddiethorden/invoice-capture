import React from "react";

// Colour communicates status, and only status. Each state also carries a
// distinct line weight and dash pattern so the screen stays usable under
// colour-vision deficiency (roughly one man in twelve).
const STATUS_STYLE = {
  green: { stroke: "#1a7f37", width: 1.5, dash: "none" },
  amber: { stroke: "#bf8700", width: 3, dash: "none" },
  red: { stroke: "#cf222e", width: 4, dash: "none" },
  grey: { stroke: "#8c959f", width: 1.5, dash: "5,4" },
};

/**
 * The left half: the invoice pages with an SVG overlay carrying the field
 * boxes. Boxes are stored normalized (0-1) and drawn in a 0..1 viewBox, so
 * they stay aligned with the page under any display size.
 */
export default function InvoiceViewer({ invoice, fields, activeKey, onPick }) {
  return (
    <div className="viewer">
      {invoice.pages.map((page) => {
        const pageFields = fields.filter(
          (f) => f.box && f.page === page.page
        );
        return (
          <div className="page" key={page.page}>
            <img
              src={page.image_url}
              alt={`Invoice page ${page.page + 1}`}
              draggable={false}
            />
            <svg
              className="overlay"
              viewBox="0 0 1 1"
              preserveAspectRatio="none"
            >
              {pageFields.map((f) => {
                const s = STATUS_STYLE[f.status] || STATUS_STYLE.green;
                const active = f.key === activeKey;
                const dim = activeKey && !active;
                return (
                  <rect
                    key={f.key}
                    data-box={f.key}
                    x={f.box.x0}
                    y={f.box.y0}
                    width={Math.max(0, f.box.x1 - f.box.x0)}
                    height={Math.max(0, f.box.y1 - f.box.y0)}
                    fill={active ? "rgba(9,105,218,0.18)" : "transparent"}
                    stroke={active ? "#0969da" : s.stroke}
                    strokeWidth={active ? 4 : s.width}
                    strokeDasharray={s.dash === "none" ? undefined : s.dash}
                    vectorEffect="non-scaling-stroke"
                    opacity={dim ? 0.25 : 1}
                    style={{ cursor: "pointer" }}
                    onClick={() => onPick(f.key)}
                  />
                );
              })}
            </svg>
          </div>
        );
      })}
    </div>
  );
}
