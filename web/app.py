"""Frontend for the lead qualifier: paste raw notes, see the audited verdict.

The page deliberately shows the whole audit trail, not just a number: the score with the
reason that reconciles to it, the two independent readings side by side, and, when they
disagree about which rules fire, the EXCLUDED abstention with the rule that flipped. The
point of the product is visible on the screen.
"""

from __future__ import annotations

import html
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from agents.runner import qualify  # noqa: E402

app = FastAPI(title="Lead Quorum")

SAMPLE = (
    "Acme Corp, industrial supplier. About 30 employees. They renewed their contract last "
    "year. Main contact is the VP of Operations. Spends around $6,000 per month."
)

_VERDICT_COLORS = {
    "CONFIRMED": "#1f9d55",
    "REVIEW": "#c98a00",
    "EXCLUDED": "#c1121f",
}

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lead Quorum</title>
<style>
  :root {{ --brand:#6E56CF; }}
  * {{ box-sizing:border-box; }}
  body {{ font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; max-width:820px;
         margin:2rem auto; padding:0 1rem; color:#1a1a2e; }}
  h1 {{ color:var(--brand); margin-bottom:.25rem; }}
  p.sub {{ color:#555; margin-top:0; }}
  textarea {{ width:100%; min-height:120px; padding:.7rem; border:1px solid #ccc;
             border-radius:8px; font:inherit; }}
  button {{ background:var(--brand); color:#fff; border:0; padding:.6rem 1.2rem;
           border-radius:8px; font-size:1rem; cursor:pointer; margin-top:.6rem; }}
  .badge {{ display:inline-block; padding:.25rem .7rem; border-radius:999px; color:#fff;
           font-weight:600; }}
  .card {{ border:1px solid #e2e2ea; border-radius:12px; padding:1rem 1.2rem; margin-top:1rem; }}
  .reason {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; background:#f6f6fb;
            padding:.6rem .8rem; border-radius:8px; white-space:pre-wrap; }}
  .cols {{ display:flex; gap:1rem; flex-wrap:wrap; }}
  .col {{ flex:1 1 240px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
  td,th {{ text-align:left; padding:.3rem .4rem; border-bottom:1px solid #eee; }}
  .drift td {{ background:#fff6e6; }}
  .flip td {{ background:#fde8e8; }}
  small {{ color:#666; }}
</style></head>
<body>
<h1>Lead Quorum</h1>
<p class="sub">The model proposes the signals, the code disposes the score, and two independent readings must agree before the number is trusted.</p>
<form method="post" action="/qualify">
  <textarea name="notes" placeholder="Paste raw lead notes...">{sample}</textarea>
  <button type="submit">Qualify</button>
</form>
{result}
</body></html>"""


def _render_result(r: dict) -> str:
    verdict = r.get("verdict") or {}
    status = verdict.get("status", "UNKNOWN")
    color = _VERDICT_COLORS.get(status, "#666")
    score = verdict.get("score")
    score_txt = "abstained" if score is None else f"{score}/100"
    reason = html.escape(verdict.get("reason", ""))

    enriched, rederived = r.get("enriched", {}), r.get("rederived", {})
    corr = verdict.get("corroboration", {}) or {}
    deltas = {d["field"]: d for d in corr.get("deltas", [])}

    fields = ["monthly_spend", "seats", "contact_role", "renewed", "industry"]
    rows = []
    # map scoring-field flips back to the lead field they read
    flip_fields = {"budget": "monthly_spend", "team_size": "seats",
                   "decision_maker": "contact_role", "prior_relationship": "renewed"}
    flipped = {flip_fields.get(d["field"], d["field"]) for d in corr.get("deltas", [])
               if d.get("effect") == "rule_flipped"}
    drifted = {d["field"] for d in corr.get("deltas", []) if d.get("effect") == "value_drift"}
    for f in fields:
        cls = "flip" if f in flipped else ("drift" if f in drifted else "")
        rows.append(
            f'<tr class="{cls}"><td>{f}</td><td>{html.escape(str(enriched.get(f, "")))}</td>'
            f'<td>{html.escape(str(rederived.get(f, "")))}</td></tr>'
        )
    table = (
        "<table><tr><th>field</th><th>reading A</th><th>reading B</th></tr>"
        + "".join(rows)
        + "</table>"
    )

    return f"""
<div class="card">
  <span class="badge" style="background:{color}">{status}</span>
  <strong style="margin-left:.6rem;font-size:1.2rem">{score_txt}</strong>
  <div class="reason" style="margin-top:.6rem">{reason}</div>
  <p style="margin-top:1rem"><strong>Two independent readings</strong>
     <small>(highlighted rows disagree; red = a rule flipped, so the score is not trusted)</small></p>
  {table}
</div>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE.format(sample=html.escape(SAMPLE), result="")


@app.post("/qualify", response_class=HTMLResponse)
async def do_qualify(notes: str = Form(...)) -> str:
    result = await qualify(notes)
    return _PAGE.format(sample=html.escape(notes), result=_render_result(result))


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
