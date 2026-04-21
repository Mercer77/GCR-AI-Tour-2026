#!/usr/bin/env python3
"""Run the Lab-01 Tech Insight pipeline locally without gh-aw."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

LAB_DIR = Path(__file__).resolve().parent
REPO_ROOT = LAB_DIR.parent
sys.path.insert(0, str(LAB_DIR / "mcp-scripts"))

from tech_insight_tools import (  # noqa: E402
    tech_cluster_or_fallback,
    tech_fetch_all_to_disk,
    tech_insight_or_fallback,
    tech_load_articles_from_disk,
    tech_read_source_list,
    tech_render_report_or_fallback,
)


def _resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_zh_markdown(
    *,
    source_label: str,
    clusters: dict[str, Any],
    insights: dict[str, Any],
) -> str:
    hotspots_val = clusters.get("hotspots")
    hotspots = hotspots_val if isinstance(hotspots_val, list) else []
    insights_val = insights.get("insights")
    insight_list = insights_val if isinstance(insights_val, list) else []
    insight_by_id = {
        str(x.get("hotspot_id") or ""): x for x in insight_list if isinstance(x, dict)
    }

    trends = [
        h
        for h in hotspots
        if isinstance(h, dict) and str(h.get("category") or "").strip() == "trend"
    ]
    singles = [
        h
        for h in hotspots
        if isinstance(h, dict) and str(h.get("category") or "").strip() != "trend"
    ]

    lines: list[str] = []
    lines.append("# 纺织行业热点报告")
    lines.append("")
    lines.append(
        f"> 生成时间：{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"
    )
    lines.append(f"> 来源配置：`{source_label}`")
    lines.append(
        f"> 热点总数：{len(hotspots)}（跨源趋势 {len(trends)}，重点单条 {len(singles)}）"
    )
    lines.append("")
    lines.append("## 24h 摘要")
    lines.append("")
    lines.append(
        "本报告基于纺织相关 RSS 信源自动聚合生成，重点覆盖产业政策、供需与价格、可持续转型、设备与制造升级等方向。"
    )
    lines.append("")

    lines.append("## Cross-source Trends（跨源趋势）")
    lines.append("")
    if not trends:
        lines.append("当前暂无跨源共振趋势。")
        lines.append("")
    for h in trends:
        hid = str(h.get("hotspot_id") or "")
        title = str(h.get("title") or "未命名热点")
        score = int(h.get("overall_heat_score") or 0)
        insight = insight_by_id.get(hid, {})
        lines.append(f"### {hid} · {title}")
        lines.append(f"- 热度：{score}")
        what_changed = str(insight.get("what_changed") or "").strip()
        why_it_matters = str(insight.get("why_it_matters") or "").strip()
        if what_changed:
            lines.append(f"- 发生了什么：{what_changed}")
        if why_it_matters:
            lines.append(f"- 为什么重要：{why_it_matters}")
        actions_val = insight.get("next_actions")
        actions = (
            [str(x) for x in actions_val if isinstance(x, str) and x.strip()]
            if isinstance(actions_val, list)
            else []
        )
        if actions:
            lines.append("- 建议动作：")
            for action in actions[:3]:
                lines.append(f"  - {action}")
        samples_val = h.get("samples")
        samples = samples_val if isinstance(samples_val, list) else []
        if samples:
            lines.append("- 参考链接：")
            for s in samples[:3]:
                if not isinstance(s, dict):
                    continue
                st = str(s.get("title") or "").strip()
                su = str(s.get("url") or "").strip()
                if su:
                    lines.append(f"  - [{st}]({su})" if st else f"  - {su}")
        lines.append("")

    lines.append("## High-signal Singles（重点单条）")
    lines.append("")
    if not singles:
        lines.append("当前暂无高信号单条更新。")
        lines.append("")
    for h in singles:
        hid = str(h.get("hotspot_id") or "")
        title = str(h.get("title") or "未命名热点")
        score = int(h.get("overall_heat_score") or 0)
        insight = insight_by_id.get(hid, {})
        lines.append(f"### {hid} · {title}")
        lines.append(f"- 热度：{score}")
        lines.append(
            f"- 发生了什么：{str(insight.get('what_changed') or '该条目为单点高信号更新，建议结合原始来源核验。')}"
        )
        lines.append(
            f"- 为什么重要：{str(insight.get('why_it_matters') or '该更新可能影响纺织行业供应链、成本或产品策略。')}"
        )
        lines.append("")

    lines.append("## Company Radar（企业雷达）")
    lines.append("")
    company_to_hotspots: dict[str, list[str]] = {}
    for h in hotspots:
        if not isinstance(h, dict):
            continue
        cov_val = h.get("coverage")
        cov = cov_val if isinstance(cov_val, dict) else {}
        companies_val = cov.get("companies")
        companies = companies_val if isinstance(companies_val, list) else []
        for c in companies:
            cs = str(c).strip()
            if not cs:
                continue
            company_to_hotspots.setdefault(cs, []).append(str(h.get("title") or ""))
    if not company_to_hotspots:
        lines.append("暂无明确公司归属的高价值热点。")
        lines.append("")
    else:
        for c, hs in sorted(company_to_hotspots.items(), key=lambda kv: kv[0]):
            lines.append(f"### {c}")
            for t in hs[:5]:
                lines.append(f"- {t}")
            lines.append("")

    lines.append("## DevTools Releases（工具链更新）")
    lines.append("")
    lines.append("本次主题以纺织产业信息为主，工具链更新占比有限。建议重点关注制造数字化、设备自动化与质量追溯系统。")
    lines.append("")
    lines.append("## Research Watch（研究趋势）")
    lines.append("")
    lines.append("重点观察方向：可持续纤维、纺织废料回收、节能减排工艺、智能纺织设备与供应链韧性。")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    load_dotenv(LAB_DIR / ".env")

    parser = argparse.ArgumentParser(
        description="Run the Lab-01 Tech Insight pipeline locally."
    )
    parser.add_argument(
        "--source-list-path",
        default=os.getenv(
            "SOURCE_LIST_PATH", "Lab-01-Tech-Insights/input/api/rss_list.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("OUTPUT_DIR", "Lab-01-Tech-Insights/output"),
    )
    parser.add_argument(
        "--signals-dir",
        default=os.getenv("SIGNALS_DIR", "Lab-01-Tech-Insights/output/signals"),
    )
    parser.add_argument(
        "--time-window-hours",
        type=int,
        default=int(os.getenv("TIME_WINDOW_HOURS", "24")),
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=int(os.getenv("TOP_K", "12")),
    )
    parser.add_argument(
        "--max-items-per-source",
        type=int,
        default=int(os.getenv("MAX_ITEMS_PER_SOURCE", "25")),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("TIMEOUT_SECONDS", "15")),
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=int(os.getenv("MAX_CHARS", "200000")),
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse existing files in signals_dir instead of re-fetching remote sources.",
    )
    parser.add_argument(
        "--report-language",
        choices=["zh", "en"],
        default=os.getenv("REPORT_LANGUAGE", "zh"),
        help="Output language for local draft report. Default: zh.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    source_list_path = _resolve_repo_path(args.source_list_path)
    output_dir = _resolve_repo_path(args.output_dir)
    signals_dir = _resolve_repo_path(args.signals_dir)
    raw_signals_path = output_dir / "raw_signals.json"
    clusters_path = output_dir / "clusters" / "hotspots.json"
    insights_path = output_dir / "insights" / "insights.json"
    report_path = output_dir / "report.md"
    frontend_report_path = LAB_DIR / "frontend" / "report.md"

    source_list = tech_read_source_list(str(source_list_path))
    print(
        f"[lab-01] Loaded {source_list['count']} sources from {source_list_path.relative_to(REPO_ROOT)}"
    )

    if args.skip_fetch:
        print(
            f"[lab-01] Skip fetch enabled, reusing existing signals under {signals_dir.relative_to(REPO_ROOT)}"
        )
    else:
        fetch_result = tech_fetch_all_to_disk(
            source_list_path=str(source_list_path),
            signals_dir=str(signals_dir),
            timeout_seconds=args.timeout_seconds,
            max_chars=args.max_chars,
            max_items_per_source=args.max_items_per_source,
        )
        print(
            f"[lab-01] Fetch completed: {fetch_result['ok']}/{fetch_result['fetched']} sources succeeded"
        )

    raw_signals = tech_load_articles_from_disk(
        signals_dir=str(signals_dir),
        source_list_path=str(source_list_path),
        max_items_per_source=args.max_items_per_source,
        time_window_hours=args.time_window_hours,
    )
    _write_json(raw_signals_path, raw_signals)

    clusters = tech_cluster_or_fallback(
        raw_signals_json=json.dumps(raw_signals, ensure_ascii=False),
        clusters_json="",
        top_k=args.top_k,
    )
    _write_json(clusters_path, clusters)

    insights = tech_insight_or_fallback(
        clusters_json=json.dumps(clusters, ensure_ascii=False),
        insights_json="",
    )
    _write_json(insights_path, insights)

    draft_markdown = ""
    if args.report_language == "zh":
        draft_markdown = _build_zh_markdown(
            source_label=str(source_list_path.relative_to(REPO_ROOT)),
            clusters=clusters,
            insights=insights,
        )

    report = tech_render_report_or_fallback(
        clusters_json=json.dumps(clusters, ensure_ascii=False),
        insights_json=json.dumps(insights, ensure_ascii=False),
        draft_markdown=draft_markdown,
    )
    _write_text(report_path, report)
    _write_text(frontend_report_path, report)

    print(f"[lab-01] Raw signals: {raw_signals_path.relative_to(REPO_ROOT)}")
    print(f"[lab-01] Hotspots: {clusters_path.relative_to(REPO_ROOT)}")
    print(f"[lab-01] Insights: {insights_path.relative_to(REPO_ROOT)}")
    print(f"[lab-01] Report: {report_path.relative_to(REPO_ROOT)}")
    print(f"[lab-01] Frontend report: {frontend_report_path.relative_to(REPO_ROOT)}")
    print(
        f"[lab-01] Done: {len(raw_signals.get('items', []))} articles -> {len(clusters.get('hotspots', []))} hotspots"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
