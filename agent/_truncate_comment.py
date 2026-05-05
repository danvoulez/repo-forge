#!/usr/bin/env python3
"""Truncate GitHub issue comment body (size limits); stdin-safe paths only."""
from __future__ import annotations

import pathlib
import sys

MAX_CHARS = 14000


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: truncate_comment.py <src_report> <dst_comment>", file=sys.stderr)
        sys.exit(2)
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2])
    text = src.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n…(truncated — full log em `outbox/` neste Mac)…"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
