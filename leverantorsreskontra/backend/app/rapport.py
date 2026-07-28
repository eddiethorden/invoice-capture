"""Rapporter — godkända leverantörsfakturor som utskriftsvänlig HTML och CSV.

Byggs live från store.godkanda_fakturor(); ingen ögonblicksbild.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from . import validation


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            if s is not None else "")


def _iso(raw: str | None) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _fmt(d: Decimal) -> str:
    """Svenskt belopp: mellanslag som tusentalsavgränsare, komma som decimal."""
    s = f"{d.quantize(Decimal('0.01')):,.2f}"      # 1,234.56
    return s.replace(",", " ").replace(".", ",")    # 1 234,56


def _summa_per_valuta(rows: list[dict]) -> dict[str, Decimal]:
    tot: dict[str, Decimal] = {}
    for r in rows:
        belopp = validation.parse_amount(r.get("total") or "")
        if belopp is None:
            continue
        ccy = (r.get("currency") or "").upper() or "?"
        tot[ccy] = tot.get(ccy, Decimal("0")) + belopp
    return tot


_STATUS = {"granskad": ("Granskad", ""), "attesterad": ("Attesterad", " ok"),
           "avvisad": ("Avvisad", ""), "utkast": ("Utkast", "")}


def bygg_csv(rows: list[dict]) -> str:
    """CSV med semikolon (svensk Excel) och BOM för åäö."""
    lines = ["Leverantör;Fakturanr;Fakturadatum;Förfaller;Belopp;Valuta;Status"]
    for r in rows:
        etikett = _STATUS.get(r.get("attest_status"), (r.get("attest_status") or "", ""))[0]
        fält = [r.get("supplier", ""), r.get("invoice_number", ""),
                _iso(r.get("invoice_date")), _iso(r.get("due_date")),
                r.get("total", ""), r.get("currency", ""), etikett]
        lines.append(";".join(str(x).replace(";", ",") for x in fält))
    return "﻿" + "\r\n".join(lines) + "\r\n"


def bygg_html(rows: list[dict], genererad: datetime) -> str:
    datum = genererad.strftime("%Y-%m-%d")
    summor = _summa_per_valuta(rows)
    summa_str = " · ".join(f"{_fmt(v)} {c}" for c, v in summor.items()) or "0,00"
    antal = len(rows)
    n_attest = sum(1 for r in rows if r.get("attest_status") == "attesterad")
    n_gransk = antal - n_attest
    statusrad = f"{n_gransk} granskade · {n_attest} attesterade" if antal else "inga"

    trad = []
    for r in rows:
        etikett, cls = _STATUS.get(r.get("attest_status"),
                                   (r.get("attest_status") or "", ""))
        belopp = r.get("total") or "—"
        trad.append(
            f"<tr><td>{_esc(r.get('supplier'))}</td>"
            f"<td class='nr'>{_esc(r.get('invoice_number'))}</td>"
            f"<td>{_esc(_iso(r.get('invoice_date')))}</td>"
            f"<td>{_esc(_iso(r.get('due_date')))}</td>"
            f"<td class='num'>{_esc(belopp)} {_esc(r.get('currency'))}</td>"
            f"<td><span class='status{cls}'>{_esc(etikett)}</span></td></tr>")
    tbody = "\n".join(trad) or "<tr><td colspan='6' class='empty'>Inga godkända fakturor.</td></tr>"

    return f"""<!doctype html><html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Godkända leverantörsfakturor</title>
<style>
  :root{{ --paper:#f3f5f7; --panel:#fff; --ink:#131a1f; --muted:#5c6a72; --line:#dde4e8;
    --accent:#0f7b6c; --accent-ink:#0b5a4f; --soft:#e5f1ee; --good:#1a7f37; --amber:#9a6700;
    --mono:ui-monospace,SFMono-Regular,Menlo,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  @media (prefers-color-scheme:dark){{ :root{{ --paper:#0c1113; --panel:#121a1c; --ink:#e9eff0;
    --muted:#93a3a8; --line:#243033; --accent:#3fc0a9; --accent-ink:#8fe6d5; --soft:#0f2a25;
    --good:#3fb950; --amber:#d3a54a; }} }}
  *{{ box-sizing:border-box; }} body{{ margin:0; background:var(--paper); color:var(--ink);
    font-family:var(--sans); line-height:1.5; }}
  .sheet{{ max-width:820px; margin:0 auto; padding:40px 44px 56px; display:flex; flex-direction:column; gap:22px; }}
  .bar{{ display:flex; justify-content:flex-end; gap:10px; }}
  .bar a,.bar button{{ font:inherit; font-size:13px; border:1px solid var(--line); background:var(--panel);
    color:var(--ink); padding:7px 13px; border-radius:7px; text-decoration:none; cursor:pointer; }}
  .bar .prim{{ background:var(--accent); color:#fff; border-color:var(--accent); }}
  .mast{{ display:flex; justify-content:space-between; align-items:flex-start; gap:20px;
    border-bottom:2px solid var(--ink); padding-bottom:16px; }}
  .eyebrow{{ font-family:var(--mono); font-size:11.5px; letter-spacing:.14em; text-transform:uppercase;
    color:var(--accent-ink); margin:0 0 6px; }}
  h1{{ margin:0; font-size:26px; }}
  .meta{{ text-align:right; font-family:var(--mono); font-size:11.5px; color:var(--muted); line-height:1.7; }}
  .meta b{{ color:var(--ink); }}
  .tiles{{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
  .tile{{ background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
  .tile .lbl{{ font-family:var(--mono); font-size:10.5px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
  .tile .val{{ font-size:22px; font-weight:700; margin-top:4px; font-variant-numeric:tabular-nums; }}
  .tile .val.sm{{ font-size:15px; font-weight:600; }}
  .tablewrap{{ border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--panel); }}
  table{{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th,td{{ padding:10px 14px; text-align:left; border-bottom:1px solid var(--line); }}
  th{{ font-size:10.5px; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); font-weight:600;
    background:color-mix(in srgb,var(--soft) 45%,transparent); }}
  td.num,th.num{{ text-align:right; font-variant-numeric:tabular-nums; font-family:var(--mono); white-space:nowrap; }}
  td.nr{{ font-family:var(--mono); color:var(--accent-ink); }} td.empty{{ text-align:center; color:var(--muted); padding:26px; }}
  .status{{ font-family:var(--mono); font-size:11px; padding:2px 8px; border-radius:999px; white-space:nowrap;
    color:var(--amber); background:color-mix(in srgb,var(--amber) 12%,transparent); }}
  .status.ok{{ color:var(--good); background:color-mix(in srgb,var(--good) 13%,transparent); }}
  tfoot td{{ font-weight:700; border-top:2px solid var(--line); border-bottom:none; }}
  .note{{ font-size:12.5px; color:var(--muted); }} .note b{{ color:var(--ink); }}
  .sign{{ display:flex; gap:40px; margin-top:6px; padding-top:18px; border-top:1px dashed var(--line); }}
  .sign div{{ flex:1; font-family:var(--mono); font-size:11.5px; color:var(--muted); }}
  .sign .rule{{ display:block; margin-top:26px; border-top:1px solid var(--ink); padding-top:4px; }}
  @media (max-width:640px){{ .tiles{{ grid-template-columns:1fr; }} .sheet{{ padding:26px 18px; }} }}
  @media print {{ body{{ background:#fff; }} .sheet{{ padding:0; max-width:none; }} .no-print{{ display:none; }}
    thead{{ display:table-header-group; }} tr{{ break-inside:avoid; }} @page{{ margin:18mm; }} }}
</style></head><body>
<div class="sheet">
  <div class="bar no-print">
    <a href="?format=csv">Ladda ner CSV</a>
    <button class="prim" onclick="window.print()">Skriv ut / PDF</button>
  </div>
  <header class="mast">
    <div><p class="eyebrow">Leverantörsreskontra · rapport</p><h1>Godkända leverantörsfakturor</h1></div>
    <div class="meta">Genererad <b>{datum}</b><br>Urval: <b>granskade + attesterade</b></div>
  </header>
  <div class="tiles">
    <div class="tile"><div class="lbl">Antal fakturor</div><div class="val">{antal}</div></div>
    <div class="tile"><div class="lbl">Summa</div><div class="val">{summa_str}</div></div>
    <div class="tile"><div class="lbl">Status</div><div class="val sm">{statusrad}</div></div>
  </div>
  <div class="tablewrap"><table>
    <thead><tr><th>Leverantör</th><th>Fakturanr</th><th>Fakturadatum</th><th>Förfaller</th>
      <th class="num">Belopp</th><th>Status</th></tr></thead>
    <tbody>{tbody}</tbody>
    <tfoot><tr><td colspan="4">Summa ({antal} fakturor)</td><td class="num">{summa_str}</td><td></td></tr></tfoot>
  </table></div>
  <p class="note"><b>Godkänd</b> = granskad och konterad av en granskare. Attesterade är även
    godkända för bokföring (SIE4) och betalning (pain.001). Live ur leverantörsreskontran {datum}.</p>
  <div class="sign"><div>Attesterad av<span class="rule"></span></div><div>Datum<span class="rule"></span></div></div>
</div></body></html>"""
