#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

START = "<!-- COMMIT-STATS:START -->"
END = "<!-- COMMIT-STATS:END -->"


def fmt(n: str) -> str:
    try:
        v = int(n)
        return f"{v:,}"
    except ValueError:
        return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", required=True)
    ap.add_argument("--commits", required=True)
    ap.add_argument("--avg-lines", required=True)
    ap.add_argument("--avg-files", required=True)
    ap.add_argument("--insertions", required=True)
    ap.add_argument("--deletions", required=True)
    args = ap.parse_args()

    body = (
        f"{START}\n"
        f"| Metric | Value |\n"
        f"|---|---|\n"
        f"| Public repos scanned | **{fmt(args.repos)}** |\n"
        f"| Commits analyzed | **{fmt(args.commits)}** |\n"
        f"| Avg lines / commit | **{args.avg_lines}** |\n"
        f"| Avg files / commit | **{args.avg_files}** |\n"
        f"| Total insertions | **{fmt(args.insertions)}** |\n"
        f"| Total deletions | **{fmt(args.deletions)}** |\n"
        f"\n"
        f"<sub>Excludes merges, lockfiles, generated bundles, vendored deps, and commits touching &gt;500 files.</sub>\n"
        f"{END}"
    )

    readme = Path("README.md")
    text = readme.read_text(encoding="utf-8")
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        body,
        text,
        count=1,
        flags=re.DOTALL,
    )
    readme.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
