#!/usr/bin/env python3
"""Fetch real OpenStreetMap static-map snapshots for each itinerary day.

This is a build-time operation. The generated PNGs are embedded by the handbook
renderer; the travel handbook does not render live maps in the browser.
"""
from __future__ import annotations
import json, sys, urllib.parse, urllib.request
from pathlib import Path

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_map_snapshots.py destination-profile.json output-directory")
    profile = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2]) / "map-snapshots"
    out.mkdir(parents=True, exist_ok=True)
    places = {str(p.get("place_id") or p.get("id")): p for p in profile.get("places", [])}
    for index, day in enumerate(profile.get("itinerary", []), 1):
        points = []
        for stop in day.get("stops", []):
            p = places.get(str(stop.get("place_id")))
            c = (p or {}).get("coordinates") or {}
            if c.get("latitude") is not None and c.get("longitude") is not None:
                points.append(f"{c['latitude']},{c['longitude']}")
        if not points:
            continue
        lat = sum(float(x.split(",")[0]) for x in points) / len(points)
        lng = sum(float(x.split(",")[1]) for x in points) / len(points)
        markers = "|".join(points)
        query = urllib.parse.urlencode({"center": f"{lat},{lng}", "zoom": 13, "size": "900x560", "maptype": "mapnik", "markers": markers})
        url = "https://staticmap.openstreetmap.de/staticmap.php?" + query
        target = out / f"day-{index:02d}.png"
        request = urllib.request.Request(url, headers={"User-Agent": "travel-handbook-skill/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                target.write_bytes(response.read())
            print(f"PASS day {index}: {target}")
        except Exception as exc:
            print(f"FAIL day {index}: {exc}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
