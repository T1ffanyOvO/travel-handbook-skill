#!/usr/bin/env python3
"""Render a small data-driven handbook and PDF from one destination profile."""
from __future__ import annotations
import html, json, math, sys, urllib.parse
from pathlib import Path

VISUAL_THEMES = {
    "coastal": {"bg": "#f4eee5", "surface": "#fffaf4", "surface_alt": "#faf1e7", "surface_cool": "#eef5f4", "text": "#263b40", "muted": "#6d7778", "primary": "#1f6678", "primary_dark": "#173f4c", "accent": "#b7654f", "gold": "#c9954b", "warning": "#a87335", "success": "#357b69", "line": "#dfd2c4"},
    "forest": {"bg": "#f3f0e7", "surface": "#fffdf8", "surface_alt": "#f1f4ec", "surface_cool": "#e8f0e8", "text": "#263a34", "muted": "#6c7971", "primary": "#357563", "primary_dark": "#173f36", "accent": "#b7654f", "gold": "#c79a53", "warning": "#a87335", "success": "#357b69", "line": "#d9dfd5"},
    "city": {"bg": "#f1f2f3", "surface": "#fbfbfa", "surface_alt": "#edf1f5", "surface_cool": "#e7eef3", "text": "#293744", "muted": "#6d7881", "primary": "#4d6f8a", "primary_dark": "#263442", "accent": "#b7604d", "gold": "#b99658", "warning": "#a87335", "success": "#357b69", "line": "#d7dee4"},
}

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
    theme_name = profile.get("visual_theme") or "coastal"
    palette = VISUAL_THEMES.get(theme_name, VISUAL_THEMES["coastal"])
    rhythm_labels = {"relaxed": "轻松", "balanced": "均衡", "full": "充实"}
    rhythm_label = rhythm_labels.get(str(trip.get("rhythm") or "").lower(), trip.get("rhythm") or "")
    def module_shell(classes, anchor, title_text, intro_text, content):
        return "<section class='module "+classes+"' id='"+anchor+"'><div class='module-header'><h2>"+title_text+"</h2><p class='module-intro'>"+intro_text+"</p></div><div class='module-body'>"+content+"</div></section>"
    routes_path = out / "map-routes.json"
    route_days = {item.get("day"): item for item in json.loads(routes_path.read_text(encoding="utf-8")).get("days", [])} if routes_path.exists() else {}
    def day_map_url(day):
        day_places = [places.get(str(stop.get("place_id"))) for stop in day.get("stops", [])]
        day_places = [place for place in day_places if place]
        if not day_places: return ""
        def query(place):
            coordinates = place.get("coordinates") or {}
            if coordinates.get("latitude") is not None and coordinates.get("longitude") is not None:
                return str(coordinates["latitude"])+","+str(coordinates["longitude"])
            return str(place.get("map_query") or place.get("name"))
        if len(day_places) == 1:
            return "https://www.google.com/maps/search/?"+urllib.parse.urlencode({"api": "1", "query": query(day_places[0])})
        travel_mode = "driving" if any(place.get("type") == "transport" for place in day_places) else "walking"
        params = {"api": "1", "origin": query(day_places[0]), "destination": query(day_places[-1]), "travelmode": travel_mode}
        if len(day_places) > 2: params["waypoints"] = "|".join(query(place) for place in day_places[1:-1])
        return "https://www.google.com/maps/dir/?"+urllib.parse.urlencode(params)
    days = []
    for i, day in enumerate(profile["itinerary"], 1):
        segments = route_days.get(i, {}).get("segments", [])
        segments_by_pair = {(s["from_place_id"], s["to_place_id"]): s for s in segments}
        cards = []
        for stop_index, stop in enumerate(day["stops"]):
            p = places[str(stop["place_id"])]
            extra = ""
            images = p.get("images") or []
            image = p.get("image_url") or (images[0].get("file") if images and isinstance(images[0], dict) else (images[0] if images else ""))
            media = "<img class='card-media stop-image' src='"+esc(image)+"' alt='"+esc(p["name"])+"真实地点图片' loading='lazy'>" if image else "<div class='card-media stop-image empty'>地点图片待核验</div>"
            fact_rows = []
            if p.get("duration_minutes"): fact_rows.append("建议游览："+esc(p["duration_minutes"])+" 分钟")
            if p.get("hours"): fact_rows.append("开放："+esc(p["hours"]))
            if p.get("closed_days"): fact_rows.append("闭馆："+esc(p["closed_days"]))
            if p.get("reservation"): fact_rows.append("预约："+esc(p["reservation"]))
            facts = "<div class='stop-facts'>"+"".join("<span>"+row+"</span>" for row in fact_rows)+"</div>"
            map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(p.get("map_query") or p["name"]))
            cards.append("<article class='entity-card entity-card--route stop'><div class='card-body stop-copy'><b class='card-meta'>"+esc(stop.get("arrival_time") or stop.get("time") or "时间待定")+"</b><h3 class='card-title'>"+esc(p["name"])+"</h3><p class='card-description'>"+esc(p.get("description") or p.get("practical_note"))+"</p><small class='card-meta'>"+esc(p.get("area"))+extra+"</small>"+facts+"<p class='card-actions action-row'><a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a> · <a href='"+esc(p.get("source_url"))+"' target='_blank'>来源 ↗</a></p></div>"+media+"</article>")
            if stop_index < len(day["stops"]) - 1:
                next_id = day["stops"][stop_index + 1]["place_id"]
                segment = segments_by_pair.get((stop["place_id"], next_id))
                if segment:
                    is_driving = segment.get("mode") == "driving"
                    mode_label = "建议机场接驳 / 出租车" if is_driving else "建议步行"
                    minutes = max(1, round(segment.get("duration_seconds", segment["distance_meters"] / 75) / 60)) if is_driving else max(1, round(segment["distance_meters"] / 75))
                    cards.append("<div class='transport-card'><span>↓</span><b>"+esc(places[stop["place_id"]]["name"])+" → "+esc(places[next_id]["name"])+"</b><em>"+mode_label+" · "+f"{segment['distance_meters']/1000:.1f}"+" km · 约 "+str(minutes)+" 分钟</em></div>")
        snapshot = out / "map-snapshots" / f"day-{i:02d}.png"
        has_snapshot = bool(route_days.get(i, {}).get("snapshot_file")) and snapshot.exists()
        map_html = "<img style='width:100%;height:auto' src='map-snapshots/"+snapshot.name+"?v=20260916-map' alt='"+esc(day.get("theme"))+"真实地图路线截图'>" if has_snapshot else map_svg(day, places)
        all_points_url = day_map_url(day)
        day_map_action = "<p class='day-map-action'><a href='"+esc(all_points_url)+"' target='_blank'>当日全部地点地图 ↗</a><span>在地图中查看当天所有点位与路线</span></p>" if all_points_url else ""
        empty_note = ""
        days.append("<details class='day' open><summary class='head'><span>DAY "+str(i)+"</span><div><h2>"+esc(day.get("theme"))+"</h2><p>"+esc(day.get("reason") or day.get("summary"))+"</p></div><i class='chevron' aria-hidden='true'>›</i></summary><div class='map'>"+map_html+"</div>"+day_map_action+empty_note+"<div class='stops'>"+"".join(cards)+"</div></details>")
    title = profile.get("display_name") or trip.get("destination") or "旅行手册"
    css = "*{box-sizing:border-box}body{margin:0;background:#f7f2e9;color:#29251f;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.7}main{max-width:1100px;margin:auto;padding:24px}header{background:linear-gradient(135deg,#2d3f36,#a75a48);color:white;border-radius:26px;padding:56px 42px;margin-bottom:20px}h1,h2,h3{font-family:Georgia,'Songti SC',serif;font-weight:500}h1{font-size:clamp(42px,8vw,82px);line-height:1;margin:18px 0}h2{font-size:34px;margin:5px 0}.download{display:inline-block;color:#fff;background:#ad4e42;padding:12px 18px;border-radius:99px;text-decoration:none;margin-top:18px}.day,.module{background:#fffdf8;border:1px solid #e8ddcf;border-radius:22px;padding:26px;margin:22px 0;break-inside:avoid}.head{display:flex;gap:20px}.head>span{color:#a94e42;font-weight:700}.map svg,.map img{display:block;width:100%;height:auto;margin:20px 0}.map svg circle{fill:#a94e42}.map svg text{fill:white;font-weight:700;font-size:14px}.map svg .label{fill:#554b42;font-weight:500;font-size:12px}.stops{display:grid;grid-template-columns:1fr;gap:14px}.stop{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:18px;align-items:start;border-left:3px solid #d5a16d;padding:16px;background:#fbf5eb}.stop h3{margin:2px 0;font-size:23px}.stop p{margin:6px 0;font-size:14px}.stop small{color:#766d63}.stop-image{width:240px;height:160px;object-fit:cover;border-radius:12px;background:#eadfce}.stop-image.empty{display:flex;align-items:center;justify-content:center;color:#85796c;font-size:13px}.module-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.module-card{background:#fbf5eb;padding:14px;border-left:3px solid #d5a16d}a{color:#9d493e}footer{padding:25px 0 60px;color:#756d63}@media(max-width:700px){main{padding:12px}header{padding:35px 24px}.head{display:block}.stop{grid-template-columns:1fr}.stop-image{width:100%;height:220px}.module-grid{grid-template-columns:1fr}}@media print{body{background:#fff}main{max-width:none;padding:0}header{color:#000;background:#fff;border:1px solid #ddd}.download{display:none}.day,.module{box-shadow:none}}"
    places_by_type = {}
    for p in places.values(): places_by_type.setdefault(p.get("type", "other"), []).append(p)
    def module(title_text, items, anchor):
        cards = "".join("<article class='module-card'><h3>"+esc(p.get("name"))+"</h3><p>"+esc(p.get("description") or p.get("practical_note"))+"</p><small>"+esc(p.get("area"))+" · <a href='"+esc(p.get("source_url"))+"' target='_blank'>来源 ↗</a></small></article>" for p in items)
        return "<section class='module' id='"+anchor+"'><h2>"+title_text+"</h2><div class='module-grid'>"+cards+"</div></section>"
    def place_image(place):
        images = place.get("images") or []
        return place.get("image_url") or (images[0].get("file") if images and isinstance(images[0], dict) else (images[0] if images else ""))
    def restaurant_card(place):
        image = place_image(place)
        map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(place.get("map_query") or place.get("name") or place.get("display_name")))
        budget = "<span class='restaurant-budget'>人均预算："+esc(place.get("price_per_person"))+"</span>" if place.get("price_per_person") else ""
        return "<article class='entity-card entity-card--restaurant restaurant-card'><img class='card-media' src='"+esc(image)+"' alt='"+esc(place.get("display_name"))+"门店图片' loading='lazy'><div class='card-body'><p class='card-meta restaurant-meta'>"+esc(place.get("cuisine"))+" · "+esc(place.get("area"))+"</p><h3 class='card-title'>"+esc(place.get("display_name"))+"</h3><p class='card-description'><b>招牌菜：</b>"+esc(place.get("signature_dishes"))+"</p><p class='card-description'><b>推荐安排：</b>"+esc(place.get("recommended_day"))+"</p><p class='card-facts'><b>营业：</b>"+esc(place.get("hours"))+" · "+esc(place.get("closed_days"))+"</p><div class='card-actions action-row restaurant-foot'>"+budget+"<a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a><a href='"+esc(place.get("source_url"))+"' target='_blank'>来源 ↗</a></div></div></article>"
    food_model = profile.get("module_groups", {}).get("food", {})
    restaurants = places_by_type.get("restaurant", [])
    restaurant_cards = "".join(restaurant_card(place) for place in restaurants)
    snack_cards = "".join("<article class='entity-card entity-card--snack snack-card'><div class='card-body'><h3 class='card-title'>"+esc(item.get("local_name") or item.get("name"))+"</h3><small class='card-meta'>"+esc(item.get("english_name"))+"</small><p class='card-description'>"+esc(item.get("description"))+"</p><p class='card-description'><b>为什么要试：</b>"+esc(item.get("why_try"))+"</p><p class='card-description'><b>哪里找：</b>"+esc(item.get("where_to_find"))+"</p></div></article>" for item in food_model.get("local_snacks", []))
    menu_cards = "".join("<article class='entity-card entity-card--term term-card'><b class='card-title'>"+esc(item.get("term"))+"</b><span class='card-meta'>"+esc(item.get("meaning"))+"</span></article>" for item in food_model.get("menu_primer", []))
    food_content = "<details class='fold food-chapter' open><summary>推荐餐饮 <span>"+str(len(restaurants))+" 家</span></summary><div class='restaurant-grid'>"+restaurant_cards+"</div></details><details class='fold food-chapter' open><summary>当地小食 <span>"+str(len(food_model.get("local_snacks", [])))+" 类</span></summary><div class='snack-grid'>"+snack_cards+"</div></details><details class='fold food-chapter' open><summary>菜单 / 点餐术语 <span>"+str(len(food_model.get("menu_primer", [])))+" 项</span></summary><div class='term-grid'>"+menu_cards+"</div></details>"
    food_html = module_shell("food-guide", "food", "餐饮指南", "把当地小食、菜单语言和具体餐厅放进同一套用餐决策里。", food_content)
    def experience_card(place):
        image = place_image(place)
        media = "<img class='card-media' src='"+esc(image)+"' alt='"+esc(place.get("name"))+"体验地点图片' loading='lazy'>" if image else "<div class='card-media experience-image empty'>准确图片待核验</div>"
        map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(place.get("map_query") or place.get("name")))
        schedule = place.get("scheduled_label") or place.get("recommended_day")
        facts = []
        if place.get("hours"): facts.append("开放："+esc(place.get("hours")))
        if place.get("closed_days"): facts.append("闭店："+esc(place.get("closed_days")))
        if place.get("reservation"): facts.append("预约："+esc(place.get("reservation")))
        fact_html = "<div class='experience-facts'>"+"".join("<span>"+item+"</span>" for item in facts)+"</div>" if facts else ""
        schedule_html = "<p class='experience-schedule'><b>推荐关联：</b>"+esc(schedule)+"</p>" if schedule else ""
        fit_html = "<p class='experience-fit'><b>适合这次旅行：</b>"+esc(place.get("fit_note"))+"</p>" if place.get("fit_note") else ""
        return "<article class='entity-card entity-card--experience experience-card'>"+media.replace("class='experience-image", "class='card-media experience-image")+"<div class='card-body experience-copy'><p class='card-meta experience-meta'>"+esc(place.get("area"))+" · "+esc(place.get("category"))+"</p><h3 class='card-title'>"+esc(place.get("name"))+"</h3>"+schedule_html+"<p class='card-description'>"+esc(place.get("description"))+"</p>"+fit_html+fact_html+"<div class='card-actions action-row experience-foot'><a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a><a href='"+esc(place.get("source_url"))+"' target='_blank'>官网 / 预约 ↗</a></div></div></article>"
    experience_groups = []
    for index, group in enumerate(profile.get("module_groups", {}).get("experiences", [])):
        group_items = []
        for item in group.get("items", []):
            place = places.get(str(item.get("place_id")))
            if place and place.get("type") == "experience": group_items.append(place)
        if not group_items: continue
        subtitle = "<small>"+esc(group.get("subtitle"))+"</small>" if group.get("subtitle") else ""
        open_attr = " open"
        experience_groups.append("<details class='fold experience-chapter'"+open_attr+"><summary><span><b>"+esc(group.get("title"))+"</b>"+subtitle+"</span><i aria-hidden='true'>＋</i></summary><div class='experience-grid'>"+"".join(experience_card(place) for place in group_items)+"</div></details>")
    experiences_html = module_shell("experiences", "experiences", "当地特色体验", "不额外堆叠打卡点；只保留能和这次路线、节奏与兴趣发生关联的体验。", "".join(experience_groups)) if experience_groups else ""
    def shopping_card(place):
        image = place_image(place)
        media = "<img class='card-media shopping-image' src='"+esc(image)+"' alt='"+esc(place.get("name"))+"门店图片' loading='lazy'>" if image else "<div class='card-media shopping-image empty'>准确门店图片待核验</div>"
        map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(place.get("map_query") or place.get("name")))
        schedule = place.get("scheduled_label") or place.get("recommended_day") or "按路线顺路加入"
        facts = []
        if place.get("hours"): facts.append("营业："+esc(place.get("hours")))
        if place.get("closed_days"): facts.append("闭店："+esc(place.get("closed_days")))
        fact_html = "<div class='shopping-facts'>"+"".join("<span>"+item+"</span>" for item in facts)+"</div>" if facts else ""
        highlights = "<p><b>值得逛 / 买：</b>"+esc(place.get("brand_highlights"))+"</p>" if place.get("brand_highlights") else ""
        tip = "<p class='shopping-tip'>"+esc(place.get("buying_tip"))+"</p>" if place.get("buying_tip") else ""
        return "<article class='entity-card entity-card--shopping shopping-card'>"+media.replace("class='shopping-image", "class='card-media shopping-image")+"<div class='card-body shopping-copy'><p class='card-meta shopping-meta'>"+esc(place.get("area"))+" · "+esc(place.get("category"))+"</p><h3 class='card-title'>"+esc(place.get("name"))+"</h3><p class='card-description shopping-schedule'><b>推荐关联：</b>"+esc(schedule)+"</p><p class='card-description'>"+esc(place.get("description"))+"</p>"+highlights+tip+fact_html+"<div class='card-actions action-row shopping-foot'><a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a><a href='"+esc(place.get("source_url"))+"' target='_blank'>官网 ↗</a></div></div></article>"
    shopping_items = []
    seen_shops = set()
    for group in profile.get("module_groups", {}).get("shopping", []):
        for item in group.get("items", []):
            place_id = str(item.get("place_id"))
            place = places.get(place_id)
            if place and place.get("type") == "shop" and place_id not in seen_shops:
                shopping_items.append(place)
                seen_shops.add(place_id)
    shopping_groups = "<details class='fold shopping-chapter' open><summary><span><b>顺路逛的店</b></span><i aria-hidden='true'>＋</i></summary><div class='shopping-grid'>"+"".join(shopping_card(place) for place in shopping_items)+"</div></details>" if shopping_items else ""
    goodies = profile.get("module_groups", {}).get("shopping_goodies", [])
    goodie_cards = "".join("<article class='entity-card entity-card--goodie goodie-card'><div class='card-body'><p class='card-meta goodie-meta'>"+esc(item.get("category"))+"</p><h3 class='card-title'>"+esc(item.get("title"))+"</h3><p class='card-description'>"+esc(item.get("description"))+"</p><p class='card-description'><b>为什么值得带走：</b>"+esc(item.get("why_buy"))+"</p><p class='card-description'><b>适合送给：</b>"+esc(item.get("best_for"))+"</p><p class='card-description'><b>哪里买：</b>"+esc(item.get("where_to_buy"))+"</p><small class='card-meta'>"+esc(item.get("buying_tip"))+"</small></div></article>" for item in goodies)
    goodies_html = "<details class='fold shopping-chapter goodies' open><summary><span><b>值得带走的当地好物</b></span><i aria-hidden='true'>＋</i></summary><div class='goodie-grid'>"+goodie_cards+"</div></details>" if goodie_cards else ""
    shopping_html = module_shell("shopping", "shopping", "购物", "把购买放在已经经过的街区；不为了清单跨区折返。", shopping_groups+goodies_html) if shopping_groups or goodies_html else ""
    language_model = profile.get("module_groups", {}).get("language", {})
    def language_set(keyword_groups, phrase_groups, label, open_attr=""):
        vocab = []
        for group in keyword_groups:
            terms = "".join("<article class='entity-card entity-card--vocab'><b class='card-title'>"+esc(item.get("term"))+"</b>"+("<small class='card-meta'>"+esc(item.get("reading"))+"</small>" if item.get("reading") else "")+"<span class='card-meta'>"+esc(item.get("meaning"))+"</span></article>" for item in group.get("items", []))
            vocab.append("<details class='fold vocab-chapter' open><summary><b>"+esc(group.get("title"))+"</b><span>"+str(len(group.get("items", [])))+" 词</span><i aria-hidden='true'>＋</i></summary><div class='vocab-items'>"+terms+"</div></details>")
        phrases = []
        for group in phrase_groups:
            rows = "".join("<article class='entity-card entity-card--phrase'><span class='card-meta'>"+str(index).zfill(2)+"</span><div class='card-body'><b class='card-title'>"+esc(item.get("sentence"))+"</b>"+("<small class='card-meta'>"+esc(item.get("reading"))+"</small>" if item.get("reading") else "")+"<em class='card-description'>"+esc(item.get("meaning"))+"</em></div><button type='button' class='card-actions copy-phrase' data-copy='"+esc(item.get("sentence"))+"'>复制</button></article>" for index, item in enumerate(group.get("items", []), 1))
            phrases.append("<details class='fold phrase-chapter' open><summary><b>"+esc(group.get("title"))+"</b><span>"+str(len(group.get("items", [])))+" 句</span><i aria-hidden='true'>＋</i></summary><div class='phrase-items'>"+rows+"</div></details>")
        if not vocab and not phrases: return ""
        return "<details class='fold language-edition'"+open_attr+"><summary><span><b>"+esc(label)+"</b></span><i aria-hidden='true'>＋</i></summary><div class='language-body'><div class='language-kicker'>高频关键词</div><div class='vocab-grid'>"+"".join(vocab)+"</div><div class='language-kicker'>现场高频句</div><div class='phrase-groups'>"+"".join(phrases)+"</div></div></details>"
    local_language = language_set(language_model.get("keyword_groups", []), language_model.get("phrase_groups", []), language_model.get("local_label", "当地语言"), " open")
    english_language = language_set(language_model.get("english_keyword_groups", []), language_model.get("english_phrase_groups", []), "英语", " open")
    language_html = module_shell("language", "language", "语言", "先用当地语言问候；需要时切换到简洁英语。每句可一键复制。", local_language+english_language) if local_language or english_language else ""
    notes_groups = []
    for index, group in enumerate(profile.get("module_groups", {}).get("travel_notes", [])):
        items = group.get("items", [])
        if not items: continue
        item_cards = "".join("<article class='entity-card entity-card--note'><div class='card-body'><h3 class='card-title'>"+esc(item.get("title"))+"</h3><p class='card-description'>"+esc(item.get("note"))+"</p></div></article>" for item in items)
        open_attr = " open"
        notes_groups.append("<details class='fold notes-chapter'"+open_attr+"><summary><span><b>"+esc(group.get("title"))+"</b></span><i aria-hidden='true'>＋</i></summary><div class='notes-grid'>"+item_cards+"</div></details>")
    notes_html = module_shell("notes", "notes", "注意事项", "把真正会影响旅途判断的事项，按场景集中在这里。", "".join(notes_groups)) if notes_groups else ""
    pending = []
    if profile.get("transport", {}).get("status") != "confirmed": pending.append("往返交通")
    if any(stay.get("status") != "confirmed" for stay in profile.get("stays", [])): pending.append("住宿")
    status_html = "<aside class='status-banner'><b>行前待确认</b><span>"+"、".join(pending)+"尚未确定；确认后会同步更新行程接驳和每日出发点。</span><a href='#preparation'>查看准备清单</a></aside>" if pending else ""
    entries = [("01", "itinerary", "每日行程", "路线、地图、交通与停留"), ("02", "food", "餐饮指南", "当地小食与餐厅"), ("03", "experiences", "当地特色体验", "可选的当地体验"), ("04", "shopping", "购物", "按路线顺路购买"), ("05", "preparation", "准备清单", "预约、证件与行前确认"), ("06", "language", "语言", "高频关键词与现场表达"), ("07", "notes", "注意事项", "天气、交通、安全与支付")]
    directory_cards = "".join("<a href='#"+anchor+"'><b>"+number+"</b><span>"+label+"</span><em>"+description+"</em></a>" for number, anchor, label, description in entries)
    directory = "<section class='contents' aria-label='旅行手册目录'><div class='contents-head'><p>CONTENTS · 随时跳转</p><h2>从这里，翻到旅途的任意一页。</h2></div><div class='contents-grid'>"+directory_cards+"</div></section>"
    prep = profile.get("handbook_preparation") or profile.get("module_groups", {}).get("preparation", {})
    confirmations = prep.get("confirmations") or prep.get("confirm_ahead", [])
    packing = prep.get("packing") or prep.get("essentials", [])
    storage_prefix = "travel-handbook:"+str(profile.get("destination", "trip"))
    def checklist(kind, index, heading, subtitle, items):
        rows = []
        for item_index, item in enumerate(items, 1):
            title_text = item.get("title", "") if isinstance(item, dict) else str(item)
            timing = item.get("timing", "") if isinstance(item, dict) else ""
            rows.append("<li><label><input type='checkbox'><span>"+str(item_index).zfill(2)+"</span><div><b>"+esc(title_text)+"</b>"+("<em>"+esc(timing)+"</em>" if timing else "")+"</div></label></li>")
        return "<section class='checklist-group' data-checklist='"+kind+"' data-storage-key='"+esc(storage_prefix+":"+kind)+"'><header><span>"+index+"</span><div><h3>"+heading+"</h3><p>"+subtitle+"</p></div><b class='check-progress'>0 / "+str(len(items))+(" 已确认" if kind == "confirmations" else " 已准备")+"</b></header><div class='progress-track'><i></i></div><ol>"+"".join(rows)+"</ol></section>"
    preparation_html = module_shell("preparation", "preparation", "准备清单", "把预约、资料和行李集中在同一页完成。勾选进度会自动保存在这台设备上。", checklist("confirmations", "01", "预约与确认", "按出发时间倒排，先锁定真正影响行程的事项。", confirmations)+checklist("packing", "02", "行李与随身物品", "出发前逐项打包，避免把临时购买变成行程负担。", packing))
    adjust_days = []
    for index, day in enumerate(profile.get("itinerary", []), 1):
        adjust_stops = []
        for stop in day.get("stops", []):
            place = places.get(str(stop.get("place_id")))
            if place: adjust_stops.append({"place_id": place.get("place_id"), "name": place.get("name"), "arrival": stop.get("arrival_time") or stop.get("time") or "", "duration": stop.get("dwell_minutes") or stop.get("duration_minutes") or ""})
        adjust_days.append({"index": index, "date": day.get("date"), "theme": day.get("theme"), "stops": adjust_stops})
    adjust_data = json.dumps(adjust_days, ensure_ascii=False).replace("</", "<\\/")
    flight_summary = ""
    confirmed_flights = [leg for leg in profile.get("transport", {}).get("legs", []) if leg.get("type") == "flight"]
    if confirmed_flights:
        flight_summary = "航班："+"；".join(str(leg.get("date"))+" "+str(leg.get("from"))+" "+str(leg.get("departure_local"))+" → "+str(leg.get("to"))+" "+str(leg.get("arrival_local")) for leg in confirmed_flights)
    stay_summary = ""
    confirmed_stays = []
    for stay in profile.get("stays", []):
        place = places.get(str(stay.get("place_id")))
        if place and stay.get("status") == "confirmed": confirmed_stays.append(place.get("name")+"（"+str(stay.get("check_in"))+"—"+str(stay.get("check_out"))+"）")
    if confirmed_stays: stay_summary = "住宿："+" → ".join(confirmed_stays)
    logistics_lines = []
    if flight_summary: logistics_lines.append("<p>"+esc(flight_summary)+"</p>")
    if stay_summary: logistics_lines.append("<p>"+esc(stay_summary)+"</p>")
    logistics_html = "<div class='logistics-summary'>"+"".join(logistics_lines)+"</div>" if logistics_lines else ""
    cover_image = profile.get("cover", {}).get("image")
    cover_style = " style=\"--cover-image:url('"+esc(cover_image)+"')\"" if cover_image else ""
    body = "<header class='hero-cover'"+cover_style+"><div class='hero-cover__shade'></div><div class='hero-cover__content'><p class='hero-cover__kicker'>TRAVEL HANDBOOK · "+esc(trip.get("start_date"))+"—"+esc(trip.get("end_date"))+"</p><h1>"+esc(title)+"</h1><p class='hero-cover__meta'>"+esc(trip.get("travelers"))+" · "+esc(rhythm_label)+" · "+esc("、".join(trip.get("interests", [])))+"</p>"+logistics_html+"<div class='hero-cover__actions'><button type='button' class='download' id='print-pdf'>一键打印/保存 PDF</button><button type='button' class='adjust-link' id='open-adjust-modal'>调整行程</button></div></div></header>"+status_html+directory+"<section id='itinerary'>"+"".join(days)+"</section>"+food_html+experiences_html+shopping_html+preparation_html+language_html+notes_html+"<footer>来源与核验日期保留在各地点卡片中。</footer>"
    theme_tokens = ":root{--color-bg:"+palette["bg"]+";--color-surface:"+palette["surface"]+";--color-surface-alt:"+palette["surface_alt"]+";--color-surface-cool:"+palette["surface_cool"]+";--color-map:#f4eee3;--color-tint:#f1e2cf;--color-text:"+palette["text"]+";--color-muted:"+palette["muted"]+";--color-primary:"+palette["primary"]+";--color-primary-dark:"+palette["primary_dark"]+";--color-accent:"+palette["accent"]+";--color-gold:"+palette["gold"]+";--color-warning:"+palette["warning"]+";--color-success:"+palette["success"]+";--color-line:"+palette["line"]+"}"
    canonical_css = (Path(__file__).resolve().parent.parent / "assets" / "canonical-handbook.css").read_text(encoding="utf-8")
    adjust_css = (Path(__file__).resolve().parent.parent / "assets" / "itinerary-adjuster.css").read_text(encoding="utf-8")
    adjust_script_new = "<script>window.adjustDays="+adjust_data+";</script><script>"+(Path(__file__).resolve().parent.parent / "assets" / "itinerary-adjuster.js").read_text(encoding="utf-8")+"</script>"
    checklist_script = "<script>document.querySelectorAll('[data-checklist]').forEach(function(group){var key=group.dataset.storageKey,inputs=[].slice.call(group.querySelectorAll('input')),label=group.querySelector('.check-progress'),bar=group.querySelector('.progress-track i'),suffix=group.dataset.checklist==='confirmations'?' 已确认':' 已准备',saved=[];try{saved=JSON.parse(localStorage.getItem(key)||'[]')}catch(e){}inputs.forEach(function(input,index){input.checked=saved.indexOf(index)>-1;input.closest('li').classList.toggle('is-checked',input.checked);input.addEventListener('change',update)});function update(){var checked=[];inputs.forEach(function(input,index){if(input.checked)checked.push(index);input.closest('li').classList.toggle('is-checked',input.checked)});try{localStorage.setItem(key,JSON.stringify(checked))}catch(e){}label.textContent=checked.length+' / '+inputs.length+suffix;bar.style.width=(inputs.length?checked.length/inputs.length*100:0)+'%'}update()});document.querySelectorAll('.copy-phrase').forEach(function(button){button.addEventListener('click',function(){var text=button.dataset.copy,navigatorCopy=navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(text):Promise.reject();navigatorCopy.then(function(){button.textContent='已复制';setTimeout(function(){button.textContent='复制'},1200)}).catch(function(){button.textContent='请长按复制'})})})</script>"
    print_script = "<script>(function(){var button=document.getElementById('print-pdf');if(!button)return;var opened=[];function restore(){opened.forEach(function(item){item.node.open=item.open});opened=[]}button.addEventListener('click',function(){opened=[];document.querySelectorAll('details').forEach(function(node){opened.push({node:node,open:node.open});node.open=true});window.print()});window.addEventListener('afterprint',restore)})();</script>"
    (out/"index.html").write_text("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(title)+"旅行手册</title><style>"+theme_tokens+canonical_css+adjust_css+"</style></head><body><main>"+body+"</main>"+adjust_script_new+checklist_script+print_script+"</body></html>", encoding="utf-8")

def render_pdf(profile, places, out):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
    pdf_font = "STSong-Light"
    try:
        pdfmetrics.registerFont(TTFont("MacCJK", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
        pdf_font = "MacCJK"
    except Exception:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    for name in ["Title", "Heading1", "Heading2", "Heading3", "BodyText"]:
        styles[name].fontName = pdf_font
    styles["Title"].fontSize = 30
    styles["Title"].leading = 38
    styles["Heading1"].fontSize = 22
    styles["Heading1"].leading = 29
    styles["Heading2"].fontSize = 17
    styles["Heading2"].leading = 23
    styles["Heading3"].fontSize = 13
    styles["Heading3"].leading = 18
    styles["BodyText"].fontSize = 9.5
    styles["BodyText"].leading = 15
    styles.add(ParagraphStyle(name="Meta", parent=styles["BodyText"], textColor=colors.HexColor("#5e685f"), fontSize=8.5, leading=13))
    styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], backColor=colors.HexColor("#f1e7d7"), borderColor=colors.HexColor("#d5a16d"), borderWidth=0.5, borderPadding=8, leading=15))
    def para(value, style="BodyText"):
        return Paragraph(html.escape(str(value or "")).replace("\n", "<br/>"), styles[style])
    def section(title_text, subtitle=""):
        story.append(Spacer(1, 12))
        story.append(para(title_text, "Heading1"))
        if subtitle: story.append(para(subtitle, "Meta"))
        story.append(Spacer(1, 5))
    def place_name(place_id):
        return places.get(str(place_id), {}).get("name", str(place_id))
    title = profile.get("display_name") or "旅行手册"
    trip = profile.get("trip", {})
    story = [para(title, "Title"), para(str(trip.get("start_date"))+" - "+str(trip.get("end_date")), "Meta"), Spacer(1, 6), para("静态完整版本：所有章节内容均已展开。", "Callout")]
    transport = profile.get("transport", {})
    flight_lines = [str(leg.get("date"))+" · "+str(leg.get("from"))+" "+str(leg.get("departure_local"))+" → "+str(leg.get("to"))+" "+str(leg.get("arrival_local")) for leg in transport.get("legs", []) if leg.get("type") == "flight"]
    stay_lines = []
    for stay in profile.get("stays", []):
        if stay.get("status") == "confirmed": stay_lines.append(place_name(stay.get("place_id"))+"（"+str(stay.get("check_in"))+" - "+str(stay.get("check_out"))+"）")
    if flight_lines: story.extend([Spacer(1, 7), para("航班："+"；".join(flight_lines), "BodyText")])
    if stay_lines: story.append(para("住宿："+" → ".join(stay_lines), "BodyText"))
    section("每日行程", "路线、地图、交通与停留")
    for index, day in enumerate(profile.get("itinerary", []), 1):
        story.append(para("DAY "+str(index)+" · "+str(day.get("theme")), "Heading2"))
        story.append(para(day.get("reason") or day.get("summary"), "BodyText"))
        snapshot = out / "map-snapshots" / f"day-{index:02d}.png"
        if snapshot.exists():
            image = Image(str(snapshot))
            image._restrictSize(160*mm, 105*mm)
            story.extend([Spacer(1, 5), image])
        for stop in day.get("stops", []):
            place = places.get(str(stop.get("place_id")), {})
            facts = []
            if place.get("duration_minutes"): facts.append("建议游览 "+str(place.get("duration_minutes"))+" 分钟")
            if place.get("hours"): facts.append("开放："+str(place.get("hours")))
            if place.get("closed_days"): facts.append("闭店："+str(place.get("closed_days")))
            if place.get("reservation"): facts.append("预约："+str(place.get("reservation")))
            story.append(para((stop.get("arrival_time") or stop.get("time") or "时间待定")+" · "+str(place.get("name")), "Heading3"))
            story.append(para(str(place.get("area") or "")+(" · "+"；".join(facts) if facts else ""), "Meta"))
            story.append(para(place.get("description") or place.get("practical_note"), "BodyText"))
        story.append(Spacer(1, 8))
    food = profile.get("module_groups", {}).get("food", {})
    section("餐饮指南", "推荐餐饮、当地小食与菜单/点餐术语")
    for place in [p for p in places.values() if p.get("type") == "restaurant"]:
        story.append(para(place.get("name"), "Heading3"))
        details = [str(place.get("cuisine") or ""), str(place.get("area") or ""), "招牌菜："+str(place.get("signature_dishes") or ""), "推荐安排："+str(place.get("recommended_day") or ""), "营业："+str(place.get("hours") or "")+"；"+str(place.get("closed_days") or "")]
        if place.get("price_per_person"): details.append("人均预算："+str(place.get("price_per_person")))
        story.append(para(" · ".join(item for item in details if item), "BodyText"))
    story.append(para("当地小食", "Heading2"))
    for item in food.get("local_snacks", []): story.append(para(str(item.get("local_name"))+"："+str(item.get("description"))+"；为什么尝试："+str(item.get("why_try"))+"；哪里找："+str(item.get("where_to_find")), "BodyText"))
    story.append(para("菜单 / 点餐术语", "Heading2"))
    for item in food.get("menu_primer", []): story.append(para(str(item.get("term"))+" - "+str(item.get("meaning"))+"："+str(item.get("note")), "BodyText"))
    section("当地特色体验")
    for group in profile.get("module_groups", {}).get("experiences", []):
        story.append(para(group.get("title"), "Heading2"))
        for item in group.get("items", []):
            place = places.get(str(item.get("place_id")), {})
            story.append(para(str(place.get("name"))+" · "+str(place.get("area") or "")+"："+str(place.get("description") or "")+"；推荐关联："+str(place.get("scheduled_label") or place.get("recommended_day") or ""), "BodyText"))
    section("购物")
    for group in profile.get("module_groups", {}).get("shopping", []):
        for item in group.get("items", []):
            place = places.get(str(item.get("place_id")), {})
            story.append(para(str(place.get("name"))+" · "+str(place.get("category") or "")+"："+str(place.get("description") or "")+"；值得逛 / 买："+str(place.get("brand_highlights") or "")+"；"+str(place.get("buying_tip") or ""), "BodyText"))
    for item in profile.get("module_groups", {}).get("shopping_goodies", []): story.append(para(str(item.get("title"))+"："+str(item.get("description"))+"；适合送给："+str(item.get("best_for"))+"；哪里买："+str(item.get("where_to_buy")), "BodyText"))
    prep = profile.get("handbook_preparation") or profile.get("module_groups", {}).get("preparation", {})
    confirmations = prep.get("confirmations") or prep.get("confirm_ahead", [])
    packing = prep.get("packing") or prep.get("essentials", [])
    section("准备清单", "预约与确认、行李与随身物品")
    for heading, items in [("预约与确认", confirmations), ("行李与随身物品", packing)]:
        story.append(para(heading, "Heading2"))
        for item in items:
            label = item.get("title") if isinstance(item, dict) else item
            timing = ("（"+str(item.get("timing"))+"）") if isinstance(item, dict) and item.get("timing") else ""
            story.append(para("□ "+str(label)+timing, "BodyText"))
    language = profile.get("module_groups", {}).get("language", {})
    section("语言")
    for label, keywords, phrases in [(language.get("local_label", "当地语言"), language.get("keyword_groups", []), language.get("phrase_groups", [])), ("英语备用", language.get("english_keyword_groups", []), language.get("english_phrase_groups", []))]:
        if not keywords and not phrases: continue
        story.append(para(label, "Heading2"))
        for group in keywords:
            story.append(para(group.get("title")+"："+"；".join(str(item.get("term"))+"（"+str(item.get("meaning"))+"）" for item in group.get("items", [])), "BodyText"))
        for group in phrases:
            story.append(para(group.get("title"), "Heading3"))
            for item in group.get("items", []): story.append(para(str(item.get("sentence"))+" - "+str(item.get("meaning")), "BodyText"))
    section("注意事项")
    for group in profile.get("module_groups", {}).get("travel_notes", []):
        story.append(para(group.get("title")+" · "+str(group.get("summary") or ""), "Heading2"))
        for item in group.get("items", []): story.append(para(str(item.get("title"))+"："+str(item.get("note")), "BodyText"))
    def page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont(pdf_font, 8)
        canvas.setFillColor(colors.HexColor("#68736b"))
        canvas.drawRightString(A4[0]-18*mm, 11*mm, "巴黎旅行手册 · "+str(doc.page))
        canvas.restoreState()
    SimpleDocTemplate(str(out/"travel-handbook.pdf"), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm, title=str(title)+"旅行手册").build(story, onFirstPage=page_number, onLaterPages=page_number)

def main():
    if len(sys.argv) != 3: raise SystemExit("usage: render_handbook.py destination-profile.json output-directory")
    profile = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    profile, places = normalize(profile); render_html(profile, places, out)
    print(f"PASS rendered {out/'index.html'} with browser print/save PDF")

if __name__ == "__main__": main()
