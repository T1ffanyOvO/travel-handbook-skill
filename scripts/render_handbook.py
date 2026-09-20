#!/usr/bin/env python3
"""Render a small data-driven handbook and PDF from one destination profile."""
from __future__ import annotations
import html, json, math, sys
from pathlib import Path

def esc(v): return html.escape(str(v or ""), quote=True)

def distance(a, b):
    if not a or not b: return None
    r = 6371.0
    p1, p2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dp, dl = math.radians(b["latitude"]-a["latitude"]), math.radians(b["longitude"]-a["longitude"])
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(x))

def normalize(profile):
    places = {}
    for p in profile.get("places", []):
        pid = str(p.get("place_id") or p.get("id") or "")
        if pid:
            places[pid] = {**p, "place_id": pid, "name": p.get("name") or p.get("display_name"), "coordinates": p.get("coordinates") or {}}
    days = []
    for day in profile.get("itinerary", []):
        stops = day.get("stops") or [{"place_id": x} for x in day.get("place_ids", [])]
        days.append({**day, "stops": [s for s in stops if str(s.get("place_id")) in places]})
    return {**profile, "itinerary": days}, places

def map_svg(day, places):
    coords = [(places[s["place_id"]].get("coordinates"), places[s["place_id"]]["name"]) for s in day["stops"]]
    coords = [(c, n) for c, n in coords if c.get("latitude") is not None]
    if not coords: return "<p>暂无已核验坐标。</p>"
    lats, lngs = [c["latitude"] for c, _ in coords], [c["longitude"] for c, _ in coords]
    minlat, maxlat, minlng, maxlng = min(lats), max(lats), min(lngs), max(lngs)
    dy, dx = max(maxlat-minlat, .001), max(maxlng-minlng, .001)
    pts = []
    for i, (c, name) in enumerate(coords, 1):
        x, y = 60+(c["longitude"]-minlng)/dx*680, 350-(c["latitude"]-minlat)/dy*270
        pts.append((x, y, i, name))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
    marks = "".join(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='16'/><text x='{x:.1f}' y='{y+5:.1f}'>{i}</text><text class='label' x='{x:.1f}' y='{max(24,y-24):.1f}'>{esc(n)[:12]}</text>" for x,y,i,n in pts)
    return "<svg viewBox='0 0 800 400'><rect width='800' height='400' rx='20' fill='#f4eee3'/><polyline points='"+line+"' fill='none' stroke='#a94e42' stroke-width='5' stroke-dasharray='8 8'/><g fill='#a94e42' stroke='#fff' stroke-width='4' text-anchor='middle'>"+marks+"</g><text x='24' y='32' fill='#635a50'>路线顺序 · 直线距离示意</text></svg>"

def render_html(profile, places, out):
    trip = profile.get("trip", {})
    days = []
    for i, day in enumerate(profile["itinerary"], 1):
        cards, prev = [], None
        for stop in day["stops"]:
            p = places[str(stop["place_id"])]
            d = distance(prev, p["coordinates"])
            extra = f" · 约 {d:.1f} km 直线距离" if d is not None else ""
            cards.append("<article class='stop'><b>"+esc(stop.get("arrival_time") or stop.get("time") or "时间待定")+"</b><h3>"+esc(p["name"])+"</h3><p>"+esc(p.get("description") or p.get("practical_note"))+"</p><small>"+esc(p.get("area"))+extra+"</small><p><a href='"+esc(p.get("source_url"))+"' target='_blank'>来源 ↗</a> · 核验日期："+esc(p.get("checked_at") or profile.get("checked_at"))+"</p></article>")
            prev = p.get("coordinates")
        snapshot = out / "map-snapshots" / f"day-{i:02d}.png"
        map_html = "<img style='width:100%;height:auto' src='map-snapshots/"+snapshot.name+"' alt='"+esc(day.get("theme"))+"真实地图路线截图'>" if snapshot.exists() else map_svg(day, places)
        days.append("<section class='day'><div class='head'><span>DAY "+str(i)+"</span><div><h2>"+esc(day.get("theme"))+"</h2><p>"+esc(day.get("reason") or day.get("summary"))+"</p></div></div><div class='map'>"+map_html+"</div><div class='stops'>"+"".join(cards)+"</div></section>")
    title = profile.get("display_name") or trip.get("destination") or "旅行手册"
    css = "*{box-sizing:border-box}body{margin:0;background:#f7f2e9;color:#29251f;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7}main{max-width:1100px;margin:auto;padding:24px}header{background:linear-gradient(135deg,#2d3f36,#a75a48);color:white;border-radius:26px;padding:56px 42px;margin-bottom:20px}h1,h2,h3{font-family:Georgia,'Songti SC',serif;font-weight:500}h1{font-size:clamp(42px,8vw,82px);line-height:1;margin:18px 0}h2{font-size:34px;margin:5px 0}.download{display:inline-block;color:#fff;background:#ad4e42;padding:12px 18px;border-radius:99px;text-decoration:none;margin-top:18px}.day,.module{background:#fffdf8;border:1px solid #e8ddcf;border-radius:22px;padding:26px;margin:22px 0;break-inside:avoid}.head{display:flex;gap:20px}.head>span{color:#a94e42;font-weight:700}.map svg{display:block;width:100%;height:auto;margin:20px 0}.map svg circle{fill:#a94e42}.map svg text{fill:white;font-weight:700;font-size:14px}.map svg .label{fill:#554b42;font-weight:500;font-size:12px}.stops{display:grid;grid-template-columns:1fr;gap:14px}.stop{border-left:3px solid #d5a16d;padding:12px 16px;background:#fbf5eb}.stop h3{margin:2px 0;font-size:23px}.stop p{margin:6px 0;font-size:14px}.stop small{color:#766d63}.module-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.module-card{background:#fbf5eb;padding:14px;border-left:3px solid #d5a16d}a{color:#9d493e}footer{padding:25px 0 60px;color:#756d63}@media(max-width:700px){main{padding:12px}header{padding:35px 24px}.head{display:block}.module-grid{grid-template-columns:1fr}}@media print{body{background:#fff}main{max-width:none;padding:0}header{color:#000;background:#fff;border:1px solid #ddd}.download{display:none}.day,.module{box-shadow:none}}"
    places_by_type = {}
    for p in places.values(): places_by_type.setdefault(p.get("type", "other"), []).append(p)
    def module(title_text, items):
        cards = "".join("<article class='module-card'><h3>"+esc(p.get("name"))+"</h3><p>"+esc(p.get("description") or p.get("practical_note"))+"</p><small>"+esc(p.get("area"))+" · <a href='"+esc(p.get("source_url"))+"' target='_blank'>来源 ↗</a></small></article>" for p in items)
        return "<section class='module'><h2>"+title_text+"</h2><div class='module-grid'>"+cards+"</div></section>"
    core = module("景点", places_by_type.get("sight", [])) + module("餐饮", places_by_type.get("restaurant", []))
    optional = module("购物", places_by_type.get("shop", [])) + module("体验", places_by_type.get("experience", []))
    body = "<header><div>TRAVEL HANDBOOK · "+esc(trip.get("start_date"))+"—"+esc(trip.get("end_date"))+"</div><h1>"+esc(title)+"</h1><p>"+esc(trip.get("travelers"))+" · "+esc(trip.get("rhythm"))+" · "+esc("、".join(trip.get("interests", [])))+"</p><button type='button' class='download' id='print-pdf'>一键打印/保存 PDF</button></header>"+"".join(days)+core+"<section class='module'><h2>准备清单</h2><ul><li>证件、签证/入境要求与旅行保险</li><li>预约景点和餐厅</li><li>交通、网络、支付和舒适步行鞋</li></ul></section>"+optional+"<section class='module'><h2>注意事项</h2><ul><li>开放时间、票价和预约规则以出发前复核为准。</li><li>地图快照中的距离为直线距离，除非另有说明。</li><li>网页打印内容使用当前页面的旅行数据和清单状态。</li></ul></section><footer>来源与核验日期保留在各地点卡片中。</footer>"
    design_system = ":root{--handbook-bg:#f4eee5;--handbook-surface:#fffaf3;--handbook-ink:#263b40;--handbook-primary:#1f6678;--handbook-accent:#b7654f;--handbook-gold:#c9954b;--handbook-line:#dfd2c4}body{background:var(--handbook-bg);color:var(--handbook-ink)}a{color:var(--handbook-primary)}header{background:linear-gradient(135deg,#173f4c,#267487)}.day,.module{background:var(--handbook-surface);border-color:var(--handbook-line)}.head>span{color:var(--handbook-accent)}.stop,.module-card{background:#faf2e8;border-left-color:#d4a15f}.download{background:var(--handbook-accent)}"
    design_system += ".map svg rect{fill:var(--handbook-surface)!important}.map svg polyline{stroke:var(--handbook-primary)!important}.map svg g{fill:var(--handbook-accent)!important}.map svg text{fill:var(--handbook-ink)!important}.map svg g text{fill:#fff!important}.module-card{color:var(--handbook-ink);border-color:var(--handbook-line)}"
    design_system += "@media print{body{background:var(--handbook-bg)!important;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}header{color:#fff8ec!important;background:linear-gradient(135deg,#173f4c,#267487)!important;-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}.download{display:none}.day,.module{box-shadow:none}details:not([open])>*:not(summary){display:block!important}}"
    print_script = "<script>(function(){var b=document.getElementById('print-pdf');if(!b)return;var o=[];function r(){o.forEach(function(x){x.node.open=x.open});o=[]}b.addEventListener('click',function(){o=[];document.querySelectorAll('details').forEach(function(n){o.push({node:n,open:n.open});n.open=true});window.print()});window.addEventListener('afterprint',r)})();</script>"
    (out/"index.html").write_text("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(title)+"旅行手册</title><style>"+css+design_system+"</style></head><body><main>"+body+"</main>"+print_script+"</body></html>", encoding="utf-8")

def render_pdf(profile, places, out):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "STSong-Light"
    styles["Heading2"].fontName = "STSong-Light"
    styles["Heading3"].fontName = "STSong-Light"
    styles["BodyText"].fontName = "STSong-Light"
    story = [Paragraph(str(profile.get("display_name") or "旅行手册"), styles["Title"]), Spacer(1, 8)]
    for i, day in enumerate(profile["itinerary"], 1):
        story.append(Paragraph(f"Day {i} · {day.get('theme','')}", styles["Heading2"]))
        story.append(Paragraph(str(day.get("reason") or day.get("summary") or ""), styles["BodyText"]))
        for stop in day["stops"]:
            p = places[str(stop["place_id"])]
            story.append(Paragraph(f"{stop.get('arrival_time') or stop.get('time') or ''} · {p['name']} · {p.get('area','')}", styles["Heading3"]))
            story.append(Paragraph(str(p.get("description") or p.get("practical_note") or ""), styles["BodyText"]))
        story.append(Spacer(1, 8))
    SimpleDocTemplate(str(out/"travel-handbook.pdf"), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm).build(story)

def main():
    if len(sys.argv) != 3: raise SystemExit("usage: render_handbook.py destination-profile.json output-directory")
    profile = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    profile, places = normalize(profile); render_html(profile, places, out)
    print(f"PASS rendered {out/'index.html'} with browser print/save PDF")

if __name__ == "__main__": main()
