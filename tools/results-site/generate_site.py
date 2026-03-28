#!/usr/bin/env python3
"""
Generate static HTML from TechEmpower FrameworkBenchmarks results.json.
Defaults to the latest results/<timestamp>/results.json by directory name.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def find_latest_results_json(repo_root: Path) -> Path:
    """Pick results/<name>/results.json where <name> is lexicographically greatest."""
    results_dir = repo_root / "results"
    if not results_dir.is_dir():
        raise FileNotFoundError(f"results directory not found: {results_dir}")

    candidates: list[tuple[str, Path]] = []
    for child in results_dir.iterdir():
        if not child.is_dir():
            continue
        rj = child / "results.json"
        if rj.is_file():
            candidates.append((child.name, rj))

    if not candidates:
        raise FileNotFoundError(
            f"No results.json found under {results_dir}"
        )

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def fmt_ts_ms(ms: Any) -> str:
    if ms is None:
        return "—"
    try:
        v = int(ms)
        return datetime.fromtimestamp(v / 1000.0, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except (TypeError, ValueError, OSError):
        return str(ms)


def collect_test_types(verify: dict[str, Any]) -> list[str]:
    types: set[str] = set()
    for _fw, mp in verify.items():
        if isinstance(mp, dict):
            types.update(mp.keys())
    return sorted(types)


def verify_cell_class(status: str | None) -> str:
    if not status:
        return "st-none"
    s = status.lower()
    if s == "pass":
        return "st-pass"
    if s == "warn":
        return "st-warn"
    if s == "fail":
        return "st-fail"
    return "st-none"


def _bench_duration_sec(st: Any, et: Any) -> float | None:
    """Duration in seconds from wrk row timestamps (TF uses Unix sec or ms epoch)."""
    try:
        fs, fe = float(st), float(et)
    except (TypeError, ValueError):
        return None
    delta = fe - fs
    if delta <= 0:
        return None
    # Millisecond epoch (e.g. 1.77e15) → delta is ms
    if min(fs, fe) >= 1e12:
        return delta / 1000.0
    # Second epoch (e.g. 1.77e9) → delta is seconds
    if min(fs, fe) >= 1e9:
        return delta
    # Legacy: duration stored as ms difference only
    return delta / 1000.0


def compute_best_rps(rows: list[dict[str, Any]]) -> float | None:
    """Best requests/sec from wrk rows (totalRequests / duration)."""
    best = 0.0
    found = False
    for row in rows:
        tr = row.get("totalRequests")
        st = row.get("startTime")
        et = row.get("endTime")
        if tr is None or st is None or et is None:
            continue
        try:
            dur = _bench_duration_sec(st, et)
            if dur and dur > 0:
                best = max(best, float(tr) / dur)
                found = True
        except (TypeError, ValueError):
            continue
    return best if found else None


def estimate_rps(rows: list[dict[str, Any]]) -> str:
    """Return estimated RPS for display from the results array elements."""
    best = compute_best_rps(rows)
    if best is not None:
        return f"{best:,.0f}"
    if rows and rows[-1].get("totalRequests") is not None:
        return f"{rows[-1]['totalRequests']:,} req (RPS N/A)"
    return "—"


BENCH_TITLES: dict[str, str] = {
    "json": "JSON",
    "plaintext": "plaintext",
    "db": "single query",
    "query": "multiple queries",
    "update": "data updates",
    "fortune": "fortunes",
    "cached-query": "cached queries",
}


def _abbr_classification(s: str) -> str:
    key = s.lower()
    m = {
        "micro": "Mcr",
        "fullstack": "Ful",
        "platform": "Plt",
        "realistic": "Rls",
    }
    return m.get(key, (s[:3] or "—").title())


def _abbr_lang(s: str) -> str:
    key = s.lower()
    m = {
        "javascript": "js",
        "typescript": "ts",
        "python": "py",
        "java": "java",
        "ruby": "rb",
        "php": "php",
        "go": "go",
        "rust": "rs",
        "csharp": "C#",
        "crystal": "cr",
        "elixir": "ex",
        "scala": "sc",
    }
    return m.get(key, s[:4] if len(s) > 4 else s)


def _abbr_short(s: str, maxlen: int = 4) -> str:
    if not s:
        return "—"
    if len(s) <= maxlen:
        return s
    return s[:maxlen]


def _bar_color_hsl(fw: str) -> str:
    """Stable hue from framework name for bar + swatch."""
    h = sum((i + 1) * ord(c) for i, c in enumerate(fw)) % 280 + 40
    return f"hsl({h}, 72%, 52%)"


def _meta_badge(val: str, kind: str) -> str:
    esc = html.escape(val)
    return f"<span class='meta-tag meta-{html.escape(kind)}'>{esc}</span>"


def _framework_meta_cells(fw: str, meta_map: dict[str, dict[str, Any]]) -> str:
    m = meta_map.get(fw, {})
    cls_ = _abbr_classification(str(m.get("classification") or ""))
    lng = _abbr_lang(str(m.get("language") or ""))
    plt = _abbr_short(str(m.get("platform") or ""), 5)
    fe = _abbr_short(str(m.get("webserver") or ""), 4)
    aos = _abbr_short(str(m.get("os") or ""), 4)
    db = _abbr_short(str(m.get("database") or ""), 4)
    dos = _abbr_short(str(m.get("database_os") or ""), 4)
    orm = _abbr_short(str(m.get("orm") or ""), 4)
    cells = [
        _meta_badge(cls_ or "—", "cls"),
        _meta_badge(lng or "—", "lng"),
        _meta_badge(plt, "plt"),
        _meta_badge(fe, "fe"),
        _meta_badge(aos, "aos"),
        _meta_badge(db, "db"),
        _meta_badge(dos, "dos"),
        _meta_badge(orm, "orm"),
    ]
    return "".join(f"<td class='meta-col'>{c}</td>" for c in cells)


def build_metadata_map(
    test_metadata: list[dict[str, Any]], framework_names: list[str]
) -> dict[str, dict[str, Any]]:
    wanted = set(framework_names)
    out: dict[str, dict[str, Any]] = {}
    for entry in test_metadata:
        name = entry.get("name")
        if name in wanted and name not in out:
            out[name] = entry
    return out


def collect_frameworks_from_raw(raw_data: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in (
        "json",
        "plaintext",
        "db",
        "query",
        "update",
        "fortune",
        "cached-query",
    ):
        block = raw_data.get(key)
        if isinstance(block, dict):
            names.update(str(k) for k in block.keys())
    return names


def render_raw_data_section(
    raw_data: dict[str, Any], meta_map: dict[str, dict[str, Any]]
) -> str:
    parts: list[str] = []
    bench_keys = (
        "json",
        "plaintext",
        "db",
        "query",
        "update",
        "fortune",
        "cached-query",
    )
    any_data = False
    meta_head = (
        "<th class='meta-col'>Cls</th>"
        "<th class='meta-col'>Lng</th>"
        "<th class='meta-col'>Plt</th>"
        "<th class='meta-col'>FE</th>"
        "<th class='meta-col'>Aos</th>"
        "<th class='meta-col'>DB</th>"
        "<th class='meta-col'>Dos</th>"
        "<th class='meta-col'>Orm</th>"
    )
    for key in bench_keys:
        block = raw_data.get(key)
        if not isinstance(block, dict) or not block:
            continue
        any_data = True
        title = BENCH_TITLES.get(key, key)
        ranked: list[tuple[str, float | None, list[dict[str, Any]]]] = []
        for fw, rows_raw in block.items():
            fw_s = str(fw)
            rows = rows_raw if isinstance(rows_raw, list) else []
            rps = compute_best_rps(rows)
            ranked.append((fw_s, rps, rows))
        ranked.sort(
            key=lambda x: (x[1] is None, -(x[1] or 0.0)),
        )
        n_fw = len(ranked)
        top = next((r for _, r, _ in ranked if r is not None and r > 0), None)

        parts.append(f'<section class="bench-block" id="raw-{html.escape(key)}">')
        parts.append(
            '<div class="bench-banner">'
            f"Best {html.escape(title)} responses per second "
            f"<span class='bench-count'>({n_fw} frameworks)</span>"
            "</div>"
        )
        parts.append('<div class="bench-table-wrap"><table class="bench-rank">')
        parts.append(
            "<thead><tr>"
            "<th class='col-rnk'>Rnk</th>"
            "<th class='col-fw'>Framework</th>"
            "<th class='col-perf'>Best performance <span class='th-hint'>(higher is better)</span></th>"
            "<th class='col-err'>Err</th>"
            f"{meta_head}"
            "<th class='meta-col note-h'>Note</th>"
            "</tr></thead><tbody>"
        )
        for i, (fw_s, rps, rows) in enumerate(ranked, start=1):
            color = _bar_color_hsl(fw_s)
            if top and rps is not None and rps > 0:
                pct = 100.0 * rps / top
                pct_s = f"{pct:.1f}%"
                bar_w = f"{min(100.0, pct):.2f}"
                rps_s = f"{rps:,.0f}"
            else:
                pct_s = "—"
                bar_w = "0"
                rps_s = "—"
            note = ""
            if rows:
                last = rows[-1]
                lat = last.get("latencyAvg")
                if lat:
                    note = f"lat {html.escape(str(lat))}"
            err_cell = "—"
            for row in rows:
                if row.get("errors") is not None:
                    err_cell = html.escape(str(row["errors"]))
                    break
            swatch = f"<span class='fw-swatch' style='background:{color}'></span>"
            parts.append(
                "<tr class='bench-row'>"
                f"<td class='col-rnk'>{i}</td>"
                f"<td class='col-fw'>{swatch}<span class='fw-name'>{html.escape(fw_s)}</span></td>"
                "<td class='col-perf'>"
                f"<div class='perf-line'>"
                f"<span class='perf-rps'>{rps_s}</span>"
                f"<span class='perf-pct'>{pct_s}</span>"
                "</div>"
                "<div class='bar-track'>"
                f"<div class='bar-fill' style='width:{bar_w}%;background-color:{color}'></div>"
                "</div>"
                "</td>"
                f"<td class='col-err'>{err_cell}</td>"
                f"{_framework_meta_cells(fw_s, meta_map)}"
                f"<td class='meta-col latency-note'>{note}</td>"
                "</tr>"
            )
        parts.append("</tbody></table></div></section>")

    if not any_data:
        parts.append(
            '<p class="note">'
            "This run has no benchmark numbers in <code>rawData</code> "
            "(wrk logs may be unprocessed, or benchmarks were not run). "
            "See the verification table above."
            "</p>"
        )
    return "\n".join(parts)


def render_page(data: dict[str, Any], source_path: Path) -> str:
    name = data.get("name", "")
    uuid_ = data.get("uuid", "")
    env_desc = data.get("environmentDescription", "")
    frameworks = data.get("frameworks") or []
    verify = data.get("verify") or {}
    completed = data.get("completed") or {}
    raw_data = data.get("rawData") or {}
    test_metadata = data.get("testMetadata") or []

    test_types = collect_test_types(verify if isinstance(verify, dict) else {})
    raw_d = raw_data if isinstance(raw_data, dict) else {}
    meta_names = sorted(
        set(str(f) for f in frameworks) | collect_frameworks_from_raw(raw_d)
    )
    meta_map = build_metadata_map(
        test_metadata if isinstance(test_metadata, list) else [], meta_names
    )

    rows_html = []
    for fw in frameworks:
        fw_s = str(fw)
        m = meta_map.get(fw_s, {})
        disp = m.get("display_name") or fw_s
        lang = m.get("language") or "—"
        meta_cell = f"{html.escape(str(disp))}<br><span class='meta'>{html.escape(str(lang))}</span>"
        comp = completed.get(fw_s, "—")
        tds = [f"<td>{html.escape(str(fw_s))}</td>", f"<td>{meta_cell}</td>"]
        tds.append(f"<td>{html.escape(str(comp))}</td>")
        for tt in test_types:
            st = None
            if isinstance(verify, dict) and fw_s in verify:
                st = verify[fw_s].get(tt)
            label = html.escape(st.upper() if st else "—")
            cls = verify_cell_class(st)
            tds.append(f"<td class='{cls}'>{label}</td>")
        rows_html.append("<tr>" + "".join(tds) + "</tr>")

    thead = (
        "<tr><th>Framework</th><th>Display name / Language</th><th>Completed</th>"
        + "".join(f"<th>{html.escape(tt)}</th>" for tt in test_types)
        + "</tr>"
    )

    git = data.get("git") or {}
    git_line = ""
    if isinstance(git, dict) and git.get("commitId"):
        cid = html.escape(str(git["commitId"])[:12])
        branch = html.escape(str(git.get("branchName", "")))
        git_line = f"<p>Git: <code>{cid}</code> ({branch})</p>"

    duration = data.get("duration")
    conc = data.get("concurrencyLevels")
    conc_s = (
        ", ".join(str(x) for x in conc)
        if isinstance(conc, list)
        else "—"
    )

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Framework Benchmarks — {html.escape(str(name))}</title>
  <style>
    :root {{
      --bg: #0f1419;
      --fg: #e7e9ea;
      --muted: #8b98a5;
      --border: #38444d;
      --pass: #00ba7c;
      --warn: #ffad1f;
      --fail: #f4212e;
      --none: #536471;
    }}
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--fg);
      margin: 0;
      padding: 1.5rem clamp(1rem, 4vw, 3rem);
      line-height: 1.5;
    }}
    h1 {{ font-size: 1.35rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.35rem; }}
    h3 {{ font-size: 1rem; margin-top: 1.25rem; }}
    .muted {{ color: var(--muted); font-size: 0.9rem; }}
    .note {{ color: var(--muted); max-width: 52rem; }}
    code {{ background: #1e2732; padding: 0.1em 0.35em; border-radius: 4px; font-size: 0.88em; }}
    .table-wrap {{ overflow-x: auto; margin: 1rem 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.88rem; min-width: 36rem; }}
    th, td {{ border: 1px solid var(--border); padding: 0.45rem 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #1a222c; position: sticky; top: 0; }}
    .meta {{ color: var(--muted); font-size: 0.85em; }}
    .st-pass {{ background: rgba(0, 186, 124, 0.12); color: var(--pass); font-weight: 600; }}
    .st-warn {{ background: rgba(255, 173, 31, 0.12); color: var(--warn); font-weight: 600; }}
    .st-fail {{ background: rgba(244, 33, 46, 0.12); color: var(--fail); font-weight: 600; }}
    .st-none {{ color: var(--none); }}
    footer {{ margin-top: 3rem; font-size: 0.8rem; color: var(--muted); }}
    .bench-block {{ margin: 2rem 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }}
    .bench-banner {{
      background: linear-gradient(180deg, #f5c518 0%, #e0b010 100%);
      color: #141414;
      font-weight: 700;
      padding: 0.55rem 1rem;
      font-size: 0.95rem;
    }}
    .bench-count {{ font-weight: 600; opacity: 0.8; margin-left: 0.25rem; }}
    .bench-table-wrap {{ overflow-x: auto; background: #161b22; }}
    table.bench-rank {{ width: 100%; min-width: 52rem; font-size: 0.82rem; border-collapse: collapse; }}
    table.bench-rank th, table.bench-rank td {{
      border-bottom: 1px solid var(--border);
      padding: 0.45rem 0.5rem;
      vertical-align: middle;
    }}
    table.bench-rank thead th {{ background: #1e2630; color: var(--fg); font-weight: 600; }}
    .th-hint {{ font-weight: 400; color: var(--muted); font-size: 0.78em; }}
    tr.bench-row:nth-child(even) {{ background: rgba(255, 255, 255, 0.035); }}
    .col-rnk {{ width: 2.5rem; text-align: right; font-weight: 700; color: var(--muted); }}
    .col-fw {{ white-space: nowrap; }}
    .fw-swatch {{
      display: inline-block;
      width: 0.55rem;
      height: 0.55rem;
      border-radius: 2px;
      margin-right: 0.4rem;
      vertical-align: middle;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.12);
    }}
    .fw-name {{ font-weight: 600; }}
    .col-perf {{ min-width: 15rem; }}
    .perf-line {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 0.75rem;
      margin-bottom: 0.3rem;
    }}
    .perf-rps {{ font-weight: 700; font-variant-numeric: tabular-nums; }}
    .perf-pct {{
      font-size: 0.85em;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      min-width: 3.6rem;
      text-align: right;
    }}
    .bar-track {{
      height: 0.5rem;
      background: rgba(255, 255, 255, 0.07);
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar-fill {{ height: 100%; border-radius: 4px; min-width: 0; }}
    .col-err {{ text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); width: 2.5rem; }}
    .meta-col {{ text-align: center; padding: 0.35rem 0.2rem !important; }}
    .note-h {{ font-size: 0.78em; }}
    .latency-note {{ text-align: left; color: var(--muted); font-size: 0.76rem; max-width: 9rem; }}
    .meta-tag {{
      display: inline-block;
      padding: 0.1em 0.32em;
      border-radius: 3px;
      font-size: 0.72rem;
      font-weight: 600;
      line-height: 1.25;
    }}
    .meta-cls {{ background: rgba(99, 102, 241, 0.35); color: #c4b5fd; }}
    .meta-lng {{ background: rgba(34, 197, 94, 0.3); color: #86efac; }}
    .meta-plt {{ background: rgba(59, 130, 246, 0.3); color: #93c5fd; }}
    .meta-fe {{ background: rgba(168, 85, 247, 0.25); color: #d8b4fe; }}
    .meta-aos {{ background: rgba(107, 114, 128, 0.35); color: #d1d5db; }}
    .meta-db {{ background: rgba(244, 63, 94, 0.28); color: #fda4af; }}
    .meta-dos {{ background: rgba(251, 146, 60, 0.25); color: #fdba74; }}
    .meta-orm {{ background: rgba(20, 184, 166, 0.28); color: #5eead4; }}
  </style>
</head>
<body>
  <h1>Framework Benchmarks Results</h1>
  <p class="muted">{html.escape(str(name))}</p>
  <p class="muted">UUID: <code>{html.escape(str(uuid_))}</code></p>
  <p class="muted">Environment: {html.escape(str(env_desc))}</p>
  {git_line}
  <p>Start: {fmt_ts_ms(data.get("startTime"))} / End: {fmt_ts_ms(data.get("completionTime"))}</p>
  <p>Test duration: {html.escape(str(duration))} s / Concurrency: {html.escape(conc_s)}</p>

  <h2>Verification (verify)</h2>
  <p class="note">Each cell is pass, warn, or fail. Use — when the framework does not implement that test type.</p>
  <div class="table-wrap">
  <table>
    <thead>{thead}</thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
  </div>

  <h2>Benchmark numbers (rawData)</h2>
  {render_raw_data_section(raw_data if isinstance(raw_data, dict) else {}, meta_map)}

  <footer>
    <p>Input: <code>{html.escape(str(source_path))}</code></p>
    <p>Generated by tools/results-site/generate_site.py</p>
  </footer>
</body>
</html>
"""
    return body


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a static site from results.json"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to results.json (default: latest under results/)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory (writes index.html)",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    src = args.input.resolve() if args.input else find_latest_results_json(repo_root)
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.html"
    try:
        src_display = src.relative_to(repo_root)
    except ValueError:
        src_display = src
    index.write_text(render_page(data, src_display), encoding="utf-8")
    print(f"Wrote {index}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
