#!/usr/bin/env python3
"""
TechEmpower FrameworkBenchmarks の results.json から静的 HTML を生成する。
入力は results/<timestamp>/results.json のうち最新のディレクトリを既定とする。
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
    """results/<name>/results.json のうち、<name> が辞書順で最大のものを選ぶ。"""
    results_dir = repo_root / "results"
    if not results_dir.is_dir():
        raise FileNotFoundError(f"results ディレクトリが見つかりません: {results_dir}")

    candidates: list[tuple[str, Path]] = []
    for child in results_dir.iterdir():
        if not child.is_dir():
            continue
        rj = child / "results.json"
        if rj.is_file():
            candidates.append((child.name, rj))

    if not candidates:
        raise FileNotFoundError(
            f"{results_dir} 配下に results.json が見つかりません"
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


def estimate_rps(rows: list[dict[str, Any]]) -> str:
    """results 配列の要素から概算 RPS を表示用に返す。"""
    best = 0.0
    for row in rows:
        tr = row.get("totalRequests")
        st = row.get("startTime")
        et = row.get("endTime")
        if tr is None or st is None or et is None:
            continue
        try:
            dur = (float(et) - float(st)) / 1000.0
            if dur > 0:
                best = max(best, float(tr) / dur)
        except (TypeError, ValueError):
            continue
    if best > 0:
        return f"{best:,.0f}"
    if rows and rows[-1].get("totalRequests") is not None:
        return f"{rows[-1]['totalRequests']:,} req (RPS 算出不可)"
    return "—"


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


def render_raw_data_section(raw_data: dict[str, Any]) -> str:
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
    for key in bench_keys:
        block = raw_data.get(key)
        if not isinstance(block, dict) or not block:
            continue
        any_data = True
        parts.append(f'<h3 id="raw-{html.escape(key)}">{html.escape(key)}</h3>')
        parts.append('<div class="table-wrap"><table><thead><tr>')
        parts.append("<th>Framework</th><th>概算 RPS</th><th>備考</th></tr></thead><tbody>")
        for fw in sorted(block.keys()):
            rows = block[fw]
            if not isinstance(rows, list):
                rows = []
            rps = estimate_rps(rows)
            note = ""
            if rows:
                last = rows[-1]
                lat = last.get("latencyAvg")
                if lat:
                    note = f"latencyAvg {html.escape(str(lat))}"
            parts.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html.escape(str(fw)),
                    html.escape(str(rps)),
                    note,
                )
            )
        parts.append("</tbody></table></div>")

    if not any_data:
        parts.append(
            '<p class="note">'
            "この run の <code>rawData</code> にはベンチマーク数値がありません"
            "（wrk 生ログ未解析、またはベンチ未実行の可能性）。"
            "検証結果は下表を参照してください。"
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
    meta_map = build_metadata_map(
        test_metadata if isinstance(test_metadata, list) else [], list(frameworks)
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
        "<tr><th>Framework</th><th>表示名 / 言語</th><th>完了時刻</th>"
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
<html lang="ja">
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
  </style>
</head>
<body>
  <h1>Framework Benchmarks 結果</h1>
  <p class="muted">{html.escape(str(name))}</p>
  <p class="muted">UUID: <code>{html.escape(str(uuid_))}</code></p>
  <p class="muted">環境: {html.escape(str(env_desc))}</p>
  {git_line}
  <p>開始: {fmt_ts_ms(data.get("startTime"))} / 終了: {fmt_ts_ms(data.get("completionTime"))}</p>
  <p>テスト継続時間: {html.escape(str(duration))} s / 並行: {html.escape(conc_s)}</p>

  <h2>検証結果（verify）</h2>
  <p class="note">各セルは pass / warn / fail。フレームワークがそのテスト種別を実装していない場合は — です。</p>
  <div class="table-wrap">
  <table>
    <thead>{thead}</thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
  </div>

  <h2>ベンチマーク数値（rawData）</h2>
  {render_raw_data_section(raw_data if isinstance(raw_data, dict) else {})}

  <footer>
    <p>入力ファイル: <code>{html.escape(str(source_path))}</code></p>
    <p>静的生成: tools/results-site/generate_site.py</p>
  </footer>
</body>
</html>
"""
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="results.json から静的サイトを生成")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="リポジトリルート（既定: カレントディレクトリ）",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="results.json のパス（未指定時は results/ 最新フォルダ）",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="出力ディレクトリ（index.html を書き込む）",
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
