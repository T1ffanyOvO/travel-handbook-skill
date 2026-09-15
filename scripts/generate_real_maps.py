#!/usr/bin/env python3
"""Build real-road walking maps and route cards from verified place coordinates."""
from __future__ import annotations

import io
import json
import math
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE_SIZE = 256
ZOOM = 14
TILE_URL = "https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png"
OSRM_URL = "https://router.project-osrm.org/route/v1/"
HEADERS = {"User-Agent": "travel-handbook-skill-v1/0.1 (static travel handbook map build)"}


def request_json(url: str) -> dict:
    return json.loads(request_bytes(url).decode("utf-8"))


def request_image(url: str) -> Image.Image:
    return Image.open(io.BytesIO(request_bytes(url))).convert("RGB")


def request_bytes(url: str) -> bytes:
    command = ["curl", "-L", "--http1.1", "--fail", "--silent", "--show-error", "--max-time", "30"]
    resolver_ip = os.environ.get("TRAVEL_OSRM_IP")
    if resolver_ip and "router.project-osrm.org" in url:
        command.extend(["--resolve", f"router.project-osrm.org:443:{resolver_ip}"])
    tile_resolver_ip = os.environ.get("TRAVEL_OSM_TILE_IP")
    if tile_resolver_ip and "a.tile.openstreetmap.fr" in url:
        command.extend(["--resolve", f"a.tile.openstreetmap.fr:443:{tile_resolver_ip}"])
    result = subprocess.run(
        command + [url],
        check=True,
        capture_output=True,
    )
    return result.stdout


def world_pixel(lng: float, lat: float, zoom: int) -> tuple[float, float]:
    scale = TILE_SIZE * (2**zoom)
    x = (lng + 180.0) / 360.0 * scale
    sin_lat = math.sin(math.radians(max(min(lat, 85.05112878), -85.05112878)))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def tile_map(points: list[tuple[float, float]]) -> tuple[Image.Image, tuple[float, float], int]:
    lng_span = max(lng for lng, _ in points) - min(lng for lng, _ in points)
    lat_span = max(lat for _, lat in points) - min(lat for _, lat in points)
    zoom = 10 if max(lng_span, lat_span) > 0.08 else ZOOM
    pixels = [world_pixel(lng, lat, zoom) for lng, lat in points]
    min_x, max_x = min(x for x, _ in pixels), max(x for x, _ in pixels)
    min_y, max_y = min(y for _, y in pixels), max(y for _, y in pixels)
    padding = 120
    left, top = min_x - padding, min_y - padding
    right, bottom = max_x + padding, max_y + padding
    tx0, ty0 = int(math.floor(left / TILE_SIZE)), int(math.floor(top / TILE_SIZE))
    tx1, ty1 = int(math.floor(right / TILE_SIZE)), int(math.floor(bottom / TILE_SIZE))
    canvas = Image.new("RGB", ((tx1 - tx0 + 1) * TILE_SIZE, (ty1 - ty0 + 1) * TILE_SIZE), "#f4efe5")
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            try:
                tile = request_image(TILE_URL.format(z=zoom, x=tx, y=ty))
                canvas.paste(tile, ((tx - tx0) * TILE_SIZE, (ty - ty0) * TILE_SIZE))
            except Exception:
                pass
    crop = (int(left - tx0*TILE_SIZE), int(top - ty0*TILE_SIZE), int(right - tx0*TILE_SIZE), int(bottom - ty0*TILE_SIZE))
    return canvas.crop(crop), (left, top), zoom


def route(a: tuple[float, float], b: tuple[float, float], profile: str) -> dict:
    coords = f"{a[0]},{a[1]};{b[0]},{b[1]}"
    payload = request_json(OSRM_URL + profile + "/" + coords + "?overview=full&geometries=geojson")
    data = payload["routes"][0]
    return {"coordinates": data["geometry"]["coordinates"], "distance_meters": round(data["distance"]), "duration_seconds": round(data["duration"])}


def label(draw: ImageDraw.ImageDraw, xy: tuple[float, float], number: int) -> None:
    x, y = xy
    draw.ellipse((x-15, y-15, x+15, y+15), fill="#6f2dbd", outline="#ffffff", width=3)
    draw.text((x, y), str(number), fill="#ffffff", anchor="mm")


def render_day(stops: list[dict], places: dict[str, dict], target: Path) -> list[dict]:
    coords = []
    for stop in stops:
        c = places[stop["place_id"]]["coordinates"]
        coords.append((float(c["longitude"]), float(c["latitude"])))
    segments = []
    route_points = list(coords)
    for index in range(len(coords) - 1):
        from_place = places[stops[index]["place_id"]]
        to_place = places[stops[index + 1]["place_id"]]
        profile = "driving" if "transport" in {from_place.get("type"), to_place.get("type")} else "foot"
        item = route(coords[index], coords[index + 1], profile)
        segments.append({"from_place_id": stops[index]["place_id"], "to_place_id": stops[index + 1]["place_id"], "mode": profile, **item})
        route_points.extend((float(lng), float(lat)) for lng, lat in item["coordinates"])
    image, origin, zoom = tile_map(route_points)
    draw = ImageDraw.Draw(image)
    route_pixels = []
    for segment in segments:
        route_pixels.extend([(world_pixel(float(lng), float(lat), zoom)[0]-origin[0], world_pixel(float(lng), float(lat), zoom)[1]-origin[1]) for lng, lat in segment["coordinates"]])
    if len(route_pixels) > 1:
        draw.line(route_pixels, fill="#2d33ff", width=7, joint="curve")
        draw.line(route_pixels, fill="#6f2dbd", width=3, joint="curve")
    for number, (lng, lat) in enumerate(coords, 1):
        px, py = world_pixel(lng, lat, zoom)
        label(draw, (px-origin[0], py-origin[1]), number)
    draw.rounded_rectangle((12, 12, 300, 46), radius=9, fill="#ffffff", outline="#d7d0c6")
    draw.text((24, 22), "道路路线 · OpenStreetMap / OSRM", fill="#37312b")
    image.save(target, "PNG")
    return segments


def main() -> int:
    if len(sys.argv) not in (3, 5) or (len(sys.argv) == 5 and sys.argv[3] != "--day"):
        raise SystemExit("usage: generate_real_maps.py destination-profile.json output-directory [--day N]")
    profile = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    output = Path(sys.argv[2])
    snapshots = output / "map-snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    places = {str(p.get("place_id") or p.get("id")): p for p in profile.get("places", [])}
    report = {"provider": "OpenStreetMap France tiles + OSRM", "checked_at": time.strftime("%Y-%m-%d"), "days": []}
    selected_day = int(sys.argv[4]) if len(sys.argv) == 5 else None
    for index, day in enumerate(profile.get("itinerary", []), 1):
        if selected_day is not None and index != selected_day:
            continue
        stops = [s for s in day.get("stops", []) if str(s.get("place_id")) in places]
        if not stops:
            continue
        target = snapshots / f"day-{index:02d}.png"
        try:
            segments = render_day(stops, places, target)
        except Exception as exc:
            print(f"FAIL day {index}: {exc}")
            continue
        report["days"].append({"day": index, "date": day.get("date"), "snapshot_file": f"map-snapshots/{target.name}", "segments": segments})
        print(f"PASS day {index}: {target}")
    (output / "map-routes.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
