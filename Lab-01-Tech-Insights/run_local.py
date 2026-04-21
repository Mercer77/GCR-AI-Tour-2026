#!/usr/bin/env python3
"""Run the Lab-01 Tech Insight pipeline locally without gh-aw."""

from __future__ import annotations

import argparse
import json
import os
import sys
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

    report = tech_render_report_or_fallback(
        clusters_json=json.dumps(clusters, ensure_ascii=False),
        insights_json=json.dumps(insights, ensure_ascii=False),
        draft_markdown="",
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
