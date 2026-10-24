"""report.html for a run: everything a reviewer needs on one page, all data escaped."""
from html import escape as e

CSS = """
body{font:15px/1.5 system-ui,sans-serif;max-width:60em;margin:2em auto;padding:0 1em;color:#1a1a1a;background:#fdfdfd}
h1{font-size:1.5em}h2{margin-top:1.6em;border-bottom:1px solid #ddd;padding-bottom:.2em}
table{border-collapse:collapse;width:100%;margin:.6em 0}td,th{border:1px solid #ddd;padding:.3em .5em;text-align:left;vertical-align:top;font-size:.92em}
th{background:#f3f3f3}.ok{color:#146c2e;font-weight:600}.bad{color:#b3261e;font-weight:600}.wait{color:#8a5a00;font-weight:600}
pre{background:#f6f6f6;padding:.7em;overflow:auto;font-size:.85em}code{font-size:.9em}
.banner{padding:.6em .9em;border-radius:6px;margin:1em 0;border:1px solid}.banner.ok{background:#e8f5ec}.banner.bad{background:#fdecea}.banner.wait{background:#fff4e0}
"""
STATUS_CLASS = {"completed": "ok", "failed": "bad", "pending": "", "in-progress": "wait"}


def _cls(ok):
    return "ok" if ok else "bad"


def render(rd):
    st = rd.read_json("state.json")
    status = st["status"]
    banner_cls = {"complete": "ok", "failed": "bad", "awaiting_approval": "wait", "interrupted": "wait"}.get(status, "wait")
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{e(st['run_id'])}</title><style>{CSS}</style></head><body>",
             f"<h1>Upgrade run {e(st['run_id'])}</h1>",
             f"<p>Cluster <code>{e(st['cluster'])}</code>, {e(st['from'])} &rarr; {e(st['target'])}, scope <code>{e(str(st['scope']))}</code>. "
             f"Simulated: no network, no real cluster.</p>"]
    msg = f"status: <b>{e(status)}</b>"
    if st.get("decision"):
        msg += f" &middot; decision: <b>{e(st['decision'])}</b>"
    if st.get("stopped_at"):
        msg += f"<br>stopped at <code>{e(st['stopped_at'])}</code>: {e(str(st.get('reason')))}"
    parts.append(f"<div class='banner {banner_cls}'>{msg}</div>")

    if rd.exists("rollback.json"):
        rb = rd.read_json("rollback.json")
        parts.append("<h2>Rollback advice (never executed by the system)</h2>")
        parts.append(f"<p>layer <code>{e(rb['layer'])}</code>; triggers fired: "
                     f"<b>{e(', '.join(rb['fired_triggers']) or 'none')}</b></p><p>{e(rb['note'])}</p>")
        acts = rb["actions"]
        if isinstance(acts, dict):
            acts = [f"{k}: {a}" for k, v in acts.items() for a in v]
        if acts:
            parts.append("<ul>" + "".join(f"<li>{e(a)}</li>" for a in acts) + "</ul>")

    if rd.exists("diff.json"):
        d = rd.read_json("diff.json")
        q = d["quadrant"]
        parts.append("<h2>Verify: version x health</h2>")
        parts.append(f"<table><tr><th></th><th>healthy</th><th>unhealthy</th></tr>"
                     f"<tr><th>target version</th><td>{'<b>proceed</b> &larr;' if q['version']=='target' and q['healthy'] else 'proceed'}</td>"
                     f"<td>{'<b>human</b> &larr;' if q['version']=='target' and not q['healthy'] else 'human'}</td></tr>"
                     f"<tr><th>old / mixed version</th><td>{'<b>rerun</b> &larr;' if q['version']=='old' and q['healthy'] else 'rerun'}</td>"
                     f"<td>{'<b>human</b> &larr;' if q['version']=='old' and not q['healthy'] else 'human'}</td></tr></table>")
        parts.append(f"<p>version state: <b>{e(d['version_state'])}</b>; decision: <b>{e(q['decision'])}</b></p>")
        parts.append("<h3>Diff against baseline</h3>")
        parts.append("<ul>" + "".join(f"<li>{e(x)}</li>" for x in d["diff"]["changed"]) + "</ul>" if d["diff"]["changed"] else "<p>no version changes</p>")
        if d["diff"]["regressions"]:
            parts.append("<p class='bad'>regressions:</p><ul>" + "".join(f"<li>{e(x)}</li>" for x in d["diff"]["regressions"]) + "</ul>")

    for title, name in (("Check criteria: baseline (before)", "snapshots/pre.json"), ("Check criteria: after", "snapshots/post.json")):
        if rd.exists(name):
            crit = rd.read_json(name)["criteria"]
            parts.append(f"<h2>{title}</h2><table><tr><th>criterion</th><th>result</th><th>detail</th></tr>")
            for r in crit:
                parts.append(f"<tr><td><code>{e(r['id'])}</code></td><td class='{_cls(r['ok'])}'>{'pass' if r['ok'] else 'FAIL'}</td><td>{e(r['detail'])}</td></tr>")
            parts.append("</table>")

    if rd.exists("plan.txt"):
        parts.append(f"<h2>Plan (dry-run)</h2><pre>{e(rd.read_text('plan.txt'))}</pre>")

    parts.append("<h2>Steps</h2><table><tr><th>step</th><th>layer</th><th>status</th><th>detail</th></tr>")
    for s in st["steps"]:
        parts.append(f"<tr><td><code>{e(s['id'])}</code></td><td>{e(str(s['layer'] or ''))}</td>"
                     f"<td class='{STATUS_CLASS.get(s['status'], '')}'>{e(s['status'])}</td><td>{e(s['detail'])}</td></tr>")
    parts.append("</table>")
    parts.append(f"<h2>Execution log</h2><pre>{e(rd.read_text('execution.log'))}</pre>")
    parts.append("</body></html>")
    return "".join(parts)


def write(rd):
    rd.write_text("report.html", render(rd))
    return rd.path / "report.html"


def write_fleet(rd, fleet_state):
    rows = "".join(f"<tr><td><code>{e(n)}</code></td><td><code>{e(r['run_id'])}</code></td><td>{e(r['status'])}</td></tr>"
                   for n, r in fleet_state["runs"].items())
    stop = (f"<div class='banner bad'>fleet paused at <code>{e(fleet_state['stopped_at'])}</code>: "
            f"a human decides how to continue</div>") if fleet_state.get("stopped_at") else ""
    html = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{e(fleet_state['fleet_run_id'])}</title>"
            f"<style>{CSS}</style></head><body><h1>Fleet run {e(fleet_state['fleet_run_id'])}</h1>{stop}"
            f"<p>Order: {e(' -> '.join(fleet_state['order']))}</p>"
            f"<table><tr><th>cluster</th><th>run</th><th>status</th></tr>{rows}</table></body></html>")
    rd.write_text("report.html", html)
