#!/usr/bin/env python3
"""Run lightweight regression suites for the content-processor skill."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
PROCESS_SCRIPT = SKILL_DIR / "scripts" / "process_share_links.py"

PRESETS = {
    "github": [
        "https://github.com/shadcn-ui/ui",
    ],
    "core": [
        "https://github.com/shadcn-ui/ui",
        "https://zhuanlan.zhihu.com/p/2004584130680230073",
        "https://blog.csdn.net/qq_19841021/article/details/146107318",
    ],
    "extended": [
        "https://github.com/shadcn-ui/ui",
        "https://zhuanlan.zhihu.com/p/2004584130680230073",
        "https://blog.csdn.net/qq_19841021/article/details/146107318",
        "https://www.toutiao.com/article/7602635061725954623/",
        "https://www.bilibili.com/video/BV1gvNieWEpt/",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run regression suites for content-processor.")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="core")
    parser.add_argument("--source", action="append", default=[], help="Extra source URL to include.")
    parser.add_argument("--analysis-mode", default="heuristic", choices=["auto", "off", "heuristic", "llm"])
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any item is not success.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = list(PRESETS[args.preset])
    sources.extend(args.source)

    with tempfile.TemporaryDirectory(prefix="content-processor-regression.") as tmp:
        command = [
            sys.executable,
            str(PROCESS_SCRIPT),
            "--report-title",
            f"regression-{args.preset}",
            "--output-root",
            tmp,
            "--analysis-mode",
            args.analysis_mode,
            *sources,
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout = result.stdout.strip()
        if not stdout:
            print(result.stderr.strip(), file=sys.stderr)
            return result.returncode or 1

        payload = json.loads(stdout)
        report_path = Path(payload["report_json"])
        report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        item_statuses = [
            {
                "platform": item.get("platform"),
                "title": item.get("title"),
                "status": item.get("status"),
                "extract_method": item.get("extract_method"),
            }
            for item in report_payload["items"]
        ]
        print(json.dumps(
            {
                "preset": args.preset,
                "status": report_payload["status"],
                "report_json": str(report_path),
                "items": item_statuses,
            },
            ensure_ascii=False,
            indent=2,
        ))

        if args.strict and any(item["status"] != "success" for item in item_statuses):
            return 1
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
