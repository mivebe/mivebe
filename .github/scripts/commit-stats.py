#!/usr/bin/env python3
"""
Walks every public repo owned by USER, runs git log against the local clone,
and aggregates commit-shape stats (avg lines / commit, avg files / commit).

Filters out noise so the averages mean something:
  - merges
  - lockfiles (package-lock, yarn.lock, pnpm-lock, etc.)
  - generated / bundled output (dist, build, .next, coverage, *.min.js, *.bundle.js, *.map)
  - vendored deps (node_modules, vendor)
  - commits touching > MAX_FILES_PER_COMMIT files (likely an initial import)

Writes results as GITHUB_OUTPUT key=value lines for the workflow step that
follows, and prints a JSON summary to stdout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

USER = "mivebe"
AUTHOR_REGEX = r"mivebe|Mihail|mihailbezev"
MAX_FILES_PER_COMMIT = 500

EXCLUDE_PATHSPECS = [
    ":(exclude)*.lock",
    ":(exclude)package-lock.json",
    ":(exclude)yarn.lock",
    ":(exclude)pnpm-lock.yaml",
    ":(exclude)composer.lock",
    ":(exclude)Gemfile.lock",
    ":(exclude)poetry.lock",
    ":(exclude)go.sum",
    ":(exclude)Cargo.lock",
    ":(exclude)*-lock.json",
    ":(exclude)dist/**",
    ":(exclude)build/**",
    ":(exclude).next/**",
    ":(exclude)out/**",
    ":(exclude)node_modules/**",
    ":(exclude)vendor/**",
    ":(exclude)coverage/**",
    ":(exclude)*.min.js",
    ":(exclude)*.bundle.js",
    ":(exclude)*.map",
]


def list_repos() -> list[str]:
    result = subprocess.run(
        ["gh", "api", f"users/{USER}/repos", "--paginate", "-q", ".[] | select(.fork == false) | .clone_url"],
        capture_output=True, text=True, check=True,
    )
    return [u for u in result.stdout.splitlines() if u.strip()]


def analyze(clone_url: str, workdir: Path) -> tuple[int, int, int, int]:
    name = clone_url.rsplit("/", 1)[-1].removesuffix(".git")
    path = workdir / name
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--no-tags", clone_url, str(path)],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError:
        return 0, 0, 0, 0

    cmd = [
        "git", "-C", str(path), "log",
        "--no-merges", "--numstat",
        f"--author={AUTHOR_REGEX}",
        "--pretty=format:COMMIT",
        "--", ".", *EXCLUDE_PATHSPECS,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout

    commits = insertions = deletions = files = 0
    cur_files = cur_ins = cur_del = 0
    seen_commit = False

    def flush() -> None:
        nonlocal commits, insertions, deletions, files
        nonlocal cur_files, cur_ins, cur_del
        if 0 < cur_files <= MAX_FILES_PER_COMMIT:
            commits += 1
            insertions += cur_ins
            deletions += cur_del
            files += cur_files
        cur_files = cur_ins = cur_del = 0

    for line in out.splitlines():
        if line.startswith("COMMIT"):
            flush()
            seen_commit = True
            continue
        if not seen_commit or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins = 0 if parts[0] == "-" else int(parts[0])
        dl = 0 if parts[1] == "-" else int(parts[1])
        cur_ins += ins
        cur_del += dl
        cur_files += 1
    flush()
    return commits, insertions, deletions, files


def main() -> None:
    repos = list_repos()
    print(f"Scanning {len(repos)} repos for {USER}...", file=sys.stderr)

    total_commits = total_ins = total_del = total_files = 0
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for url in repos:
            c, i, d, f = analyze(url, workdir)
            print(f"  {url.rsplit('/',1)[-1]}: {c} commits, {i+d} lines, {f} files", file=sys.stderr)
            total_commits += c
            total_ins += i
            total_del += d
            total_files += f

    if total_commits == 0:
        print("No commits matched the author filter.", file=sys.stderr)
        sys.exit(1)

    avg_lines = round((total_ins + total_del) / total_commits, 1)
    avg_files = round(total_files / total_commits, 1)

    stats = {
        "repos": len(repos),
        "commits": total_commits,
        "insertions": total_ins,
        "deletions": total_del,
        "lines_total": total_ins + total_del,
        "files_total": total_files,
        "avg_lines_per_commit": avg_lines,
        "avg_files_per_commit": avg_files,
    }

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            for k, v in stats.items():
                fh.write(f"{k}={v}\n")

    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
