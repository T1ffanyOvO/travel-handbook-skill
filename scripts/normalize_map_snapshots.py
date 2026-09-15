#!/usr/bin/env python3
"""Normalize generated map snapshots to the Day 2 canvas without cropping routes."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: normalize_map_snapshots.py map-snapshots-directory")
    directory = Path(sys.argv[1])
    reference = directory / "day-02.png"
    if not reference.exists():
        raise SystemExit("missing Day 2 reference map")
    target_size = Image.open(reference).size
    for path in sorted(directory.glob("day-*.png")):
        image = Image.open(path).convert("RGB")
        fitted = ImageOps.contain(image, target_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", target_size, "#f4efe5")
        offset = ((target_size[0] - fitted.width) // 2, (target_size[1] - fitted.height) // 2)
        canvas.paste(fitted, offset)
        canvas.save(path, "PNG")
        print(f"PASS {path.name}: {target_size[0]}x{target_size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
