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
 * The left half: the invoice pages with an SVG overlay carrying the boxes.
 *
 * `boxes` is a flat list of { id, page, status, box } - it carries both the
 * header fields and the line-item rows, so a click anywhere on the page maps
 * back to the right control on the right.
 */
export default function InvoiceViewer({ invoice, boxes, activeId, onPick }) {
  return (
    <div className="viewer">
      {invoice.pages.map((page) => {
        const pageBoxes = boxes.filter((b) => b.box && b.page === page.page);
        return (
          <div className="page" key={page.page}>
            <img
              src={page.image_url}
              alt={`Fakturasida ${page.page + 1}`}
              draggable={false}
            />
            <svg
              className="overlay"
              viewBox="0 0 1 1"
              preserveAspectRatio="none"
            >
              {pageBoxes.map((b) => {
                const s = STATUS_STYLE[b.status] || STATUS_STYLE.green;
                const active = b.id === activeId;
                const dim = activeId && !active;
                return (
                  <rect
                    key={b.id}
                    data-box={b.id}
                    x={b.box.x0}
                    y={b.box.y0}
                    width={Math.max(0, b.box.x1 - b.box.x0)}
                    height={Math.max(0, b.box.y1 - b.box.y0)}
                    fill={active ? "rgba(9,105,218,0.18)" : "transparent"}
                    stroke={active ? "#0969da" : s.stroke}
                    strokeWidth={active ? 4 : s.width}
                    strokeDasharray={s.dash === "none" ? undefined : s.dash}
                    vectorEffect="non-scaling-stroke"
                    opacity={dim ? 0.25 : 1}
                    style={{ cursor: "pointer" }}
                    onClick={() => onPick(b.id)}
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
