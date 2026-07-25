import React from "react";

/**
 * The allocation lines: each invoice row, coded to a Marathon project.
 * A single invoice can be split across several projects, so every row carries
 * its own project. Rows are bound to their box on the invoice, like the fields.
 */
export default function LineItems({
  items,
  projects,
  activeId,
  onPick,
  onProject,
}) {
  if (!items || items.length === 0) return null;

  const allocated = items.every((it) => it.project);

  return (
    <div className="lineitems">
      <div className="lineitems-head">
        <span>Line items → project</span>
        <span className={allocated ? "alloc-ok" : "alloc-todo"}>
          {allocated
            ? "all rows coded"
            : `${items.filter((it) => it.project).length}/${items.length} coded`}
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
                className={`row status-${it.status} ${
                  id === activeId ? "active" : ""
                }`}
                onClick={() => onPick(id)}
              >
                <td className="desc" title={it.description}>
                  {it.description || <em>(no description)</em>}
                </td>
                <td className="amt">{it.amount}</td>
                <td className="proj">
                  <select
                    value={it.project}
                    onClick={(e) => e.stopPropagation()}
                    onFocus={() => onPick(id)}
                    onChange={(e) => onProject(it.index, e.target.value)}
                  >
                    <option value="">— project —</option>
                    {projects.map((p) => (
                      <option key={p.code} value={p.code}>
                        {p.code} · {p.name}
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
