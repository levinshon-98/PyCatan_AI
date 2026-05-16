#!/usr/bin/env python3
"""Fail if files that would be committed appear to contain API keys."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


SECRET_PATTERNS = {
    "OpenRouter key": re.compile(r"sk-or-v1-[A-Za-z0-9_-]{20,}"),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9_-]{32,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{32,}"),
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "ElevenLabs key": re.compile(r"sk_[A-Za-z0-9]{20,}"),
}

TEXT_SUFFIXES = {
    ".bat",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yml",
    ".yaml",
}


def candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        path = Path(line)
        if path.suffix.lower() in TEXT_SUFFIXES and path.is_file():
            paths.append(path)
    return paths


def main() -> int:
    findings: list[str] = []
    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path}: possible {label}")

    if findings:
        print("Possible secrets found. Remove them before pushing/deploying:")
        for finding in findings:
            print(f"  - {finding}")
        return 1

    print("No API-key patterns found in committable text files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
