#!/usr/bin/env python3
"""Render a small data-driven handbook and PDF from one destination profile."""
from __future__ import annotations
import html, json, math, sys, urllib.parse
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
            media = "<img class='stop-image' src='"+esc(image)+"' alt='"+esc(p["name"])+"真实地点图片' loading='lazy'>" if image else "<div class='stop-image empty'>地点图片待核验</div>"
            fact_rows = []
            if p.get("duration_minutes"): fact_rows.append("建议游览："+esc(p["duration_minutes"])+" 分钟")
            if p.get("hours"): fact_rows.append("开放："+esc(p["hours"]))
            if p.get("closed_days"): fact_rows.append("闭馆："+esc(p["closed_days"]))
            if p.get("reservation"): fact_rows.append("预约："+esc(p["reservation"]))
            facts = "<div class='stop-facts'>"+"".join("<span>"+row+"</span>" for row in fact_rows)+"</div>"
            map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(p.get("map_query") or p["name"]))
            cards.append("<article class='stop'><div class='stop-copy'><b>"+esc(stop.get("arrival_time") or stop.get("time") or "时间待定")+"</b><h3>"+esc(p["name"])+"</h3><p>"+esc(p.get("description") or p.get("practical_note"))+"</p><small>"+esc(p.get("area"))+extra+"</small>"+facts+"<p><a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a> · <a href='"+esc(p.get("source_url"))+"' target='_blank'>来源 ↗</a></p></div>"+media+"</article>")
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
        map_html = "<img style='width:100%;height:auto' src='map-snapshots/"+snapshot.name+"' alt='"+esc(day.get("theme"))+"真实地图路线截图'>" if has_snapshot else map_svg(day, places)
        all_points_url = day_map_url(day)
        day_map_action = "<p class='day-map-action'><a href='"+esc(all_points_url)+"' target='_blank'>当日全部地点地图 ↗</a><span>在地图中查看当天所有点位与路线</span></p>" if all_points_url else ""
        empty_note = "<p class='day-empty-note'>当日只有一个核心地点，无需安排地点间移动。</p>" if len(day["stops"]) == 1 else ""
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
        return "<article class='restaurant-card'><img src='"+esc(image)+"' alt='"+esc(place.get("display_name"))+"门店图片' loading='lazy'><div><p class='restaurant-meta'>"+esc(place.get("cuisine"))+" · "+esc(place.get("area"))+"</p><h3>"+esc(place.get("display_name"))+"</h3><p><b>招牌菜：</b>"+esc(place.get("signature_dishes"))+"</p><p><b>推荐安排：</b>"+esc(place.get("recommended_day"))+"</p><p><b>营业：</b>"+esc(place.get("hours"))+" · "+esc(place.get("closed_days"))+"</p><div class='restaurant-foot'>"+budget+"<a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a><a href='"+esc(place.get("source_url"))+"' target='_blank'>来源 ↗</a></div></div></article>"
    food_model = profile.get("module_groups", {}).get("food", {})
    restaurants = places_by_type.get("restaurant", [])
    restaurant_cards = "".join(restaurant_card(place) for place in restaurants)
    snack_cards = "".join("<article class='snack-card'><h3>"+esc(item.get("local_name") or item.get("name"))+"</h3><small>"+esc(item.get("english_name"))+"</small><p>"+esc(item.get("description"))+"</p><p><b>为什么要试：</b>"+esc(item.get("why_try"))+"</p><p><b>哪里找：</b>"+esc(item.get("where_to_find"))+"</p></article>" for item in food_model.get("local_snacks", []))
    menu_cards = "".join("<article class='term-card'><b>"+esc(item.get("term"))+"</b><span>"+esc(item.get("meaning"))+"</span><p>"+esc(item.get("note"))+"</p></article>" for item in food_model.get("menu_primer", []))
    food_html = "<section class='module food-guide' id='food'><h2>餐饮指南</h2><details class='food-chapter' open><summary>推荐餐饮 <span>"+str(len(restaurants))+" 家</span></summary><div class='restaurant-grid'>"+restaurant_cards+"</div></details><details class='food-chapter' open><summary>当地小食 <span>"+str(len(food_model.get("local_snacks", [])))+" 类</span></summary><div class='snack-grid'>"+snack_cards+"</div></details><details class='food-chapter' open><summary>菜单 / 点餐术语 <span>"+str(len(food_model.get("menu_primer", [])))+" 项</span></summary><div class='term-grid'>"+menu_cards+"</div></details></section>"
    def experience_card(place):
        image = place_image(place)
        media = "<img src='"+esc(image)+"' alt='"+esc(place.get("name"))+"体验地点图片' loading='lazy'>" if image else "<div class='experience-image empty'>准确图片待核验</div>"
        map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(place.get("map_query") or place.get("name")))
        schedule = place.get("scheduled_label") or place.get("recommended_day")
        facts = []
        if place.get("hours"): facts.append("开放："+esc(place.get("hours")))
        if place.get("closed_days"): facts.append("闭店："+esc(place.get("closed_days")))
        if place.get("reservation"): facts.append("预约："+esc(place.get("reservation")))
        fact_html = "<div class='experience-facts'>"+"".join("<span>"+item+"</span>" for item in facts)+"</div>" if facts else ""
        schedule_html = "<p class='experience-schedule'><b>推荐关联：</b>"+esc(schedule)+"</p>" if schedule else ""
        fit_html = "<p class='experience-fit'><b>适合这次旅行：</b>"+esc(place.get("fit_note"))+"</p>" if place.get("fit_note") else ""
        return "<article class='experience-card'>"+media+"<div class='experience-copy'><p class='experience-meta'>"+esc(place.get("area"))+" · "+esc(place.get("category"))+"</p><h3>"+esc(place.get("name"))+"</h3>"+schedule_html+"<p>"+esc(place.get("description"))+"</p>"+fit_html+fact_html+"<div class='experience-foot'><a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a><a href='"+esc(place.get("source_url"))+"' target='_blank'>官网 / 预约 ↗</a></div></div></article>"
    experience_groups = []
    for index, group in enumerate(profile.get("module_groups", {}).get("experiences", [])):
        group_items = []
        for item in group.get("items", []):
            place = places.get(str(item.get("place_id")))
            if place and place.get("type") == "experience": group_items.append(place)
        if not group_items: continue
        subtitle = "<small>"+esc(group.get("subtitle"))+"</small>" if group.get("subtitle") else ""
        open_attr = " open"
        experience_groups.append("<details class='experience-chapter'"+open_attr+"><summary><span><b>"+esc(group.get("title"))+"</b>"+subtitle+"</span><i aria-hidden='true'>＋</i></summary><div class='experience-grid'>"+"".join(experience_card(place) for place in group_items)+"</div></details>")
    experiences_html = "<section class='module experiences' id='experiences'><h2>当地特色体验</h2><p class='experiences-intro'>不额外堆叠打卡点；只保留能和这次路线、节奏与兴趣发生关联的体验。</p>"+"".join(experience_groups)+"</section>" if experience_groups else ""
    def shopping_card(place):
        image = place_image(place)
        media = "<img src='"+esc(image)+"' alt='"+esc(place.get("name"))+"门店图片' loading='lazy'>" if image else "<div class='shopping-image empty'>准确门店图片待核验</div>"
        map_url = "https://www.google.com/maps/search/?api=1&query="+urllib.parse.quote_plus(str(place.get("map_query") or place.get("name")))
        schedule = place.get("scheduled_label") or place.get("recommended_day") or "按路线顺路加入"
        facts = []
        if place.get("hours"): facts.append("营业："+esc(place.get("hours")))
        if place.get("closed_days"): facts.append("闭店："+esc(place.get("closed_days")))
        fact_html = "<div class='shopping-facts'>"+"".join("<span>"+item+"</span>" for item in facts)+"</div>" if facts else ""
        highlights = "<p><b>值得逛 / 买：</b>"+esc(place.get("brand_highlights"))+"</p>" if place.get("brand_highlights") else ""
        tip = "<p class='shopping-tip'>"+esc(place.get("buying_tip"))+"</p>" if place.get("buying_tip") else ""
        return "<article class='shopping-card'>"+media+"<div class='shopping-copy'><p class='shopping-meta'>"+esc(place.get("area"))+" · "+esc(place.get("category"))+"</p><h3>"+esc(place.get("name"))+"</h3><p class='shopping-schedule'><b>推荐关联：</b>"+esc(schedule)+"</p><p>"+esc(place.get("description"))+"</p>"+highlights+tip+fact_html+"<div class='shopping-foot'><a href='"+esc(map_url)+"' target='_blank'>地图导航 ↗</a><a href='"+esc(place.get("source_url"))+"' target='_blank'>官网 ↗</a></div></div></article>"
    shopping_items = []
    seen_shops = set()
    for group in profile.get("module_groups", {}).get("shopping", []):
        for item in group.get("items", []):
            place_id = str(item.get("place_id"))
            place = places.get(place_id)
            if place and place.get("type") == "shop" and place_id not in seen_shops:
                shopping_items.append(place)
                seen_shops.add(place_id)
    shopping_groups = "<details class='shopping-chapter' open><summary><span><b>顺路逛的店</b><small>按区域顺路加入，具体推荐安排保留在每家店卡片中</small></span><i aria-hidden='true'>＋</i></summary><div class='shopping-grid'>"+"".join(shopping_card(place) for place in shopping_items)+"</div></details>" if shopping_items else ""
    goodies = profile.get("module_groups", {}).get("shopping_goodies", [])
    goodie_cards = "".join("<article class='goodie-card'><p class='goodie-meta'>"+esc(item.get("category"))+"</p><h3>"+esc(item.get("title"))+"</h3><p>"+esc(item.get("description"))+"</p><p><b>为什么值得带走：</b>"+esc(item.get("why_buy"))+"</p><p><b>适合送给：</b>"+esc(item.get("best_for"))+"</p><p><b>哪里买：</b>"+esc(item.get("where_to_buy"))+"</p><small>"+esc(item.get("buying_tip"))+"</small></article>" for item in goodies)
    goodies_html = "<details class='shopping-chapter goodies' open><summary><span><b>值得带走的当地好物</b><small>轻便、可分享，也不会脱离行程</small></span><i aria-hidden='true'>＋</i></summary><div class='goodie-grid'>"+goodie_cards+"</div></details>" if goodie_cards else ""
    shopping_html = "<section class='module shopping' id='shopping'><h2>购物</h2><p class='shopping-intro'>把购买放在已经经过的街区；不为了清单跨区折返。</p>"+shopping_groups+goodies_html+"</section>" if shopping_groups or goodies_html else ""
    language_model = profile.get("module_groups", {}).get("language", {})
    def language_set(keyword_groups, phrase_groups, label, open_attr=""):
        vocab = []
        for group in keyword_groups:
            terms = "".join("<article><b>"+esc(item.get("term"))+"</b>"+("<small>"+esc(item.get("reading"))+"</small>" if item.get("reading") else "")+"<span>"+esc(item.get("meaning"))+"</span></article>" for item in group.get("items", []))
            vocab.append("<details class='vocab-chapter' open><summary><b>"+esc(group.get("title"))+"</b><span>"+str(len(group.get("items", [])))+" 词</span><i aria-hidden='true'>＋</i></summary><div class='vocab-items'>"+terms+"</div></details>")
        phrases = []
        for group in phrase_groups:
            rows = "".join("<article><span>"+str(index).zfill(2)+"</span><div><b>"+esc(item.get("sentence"))+"</b>"+("<small>"+esc(item.get("reading"))+"</small>" if item.get("reading") else "")+"<em>"+esc(item.get("meaning"))+"</em></div><button type='button' class='copy-phrase' data-copy='"+esc(item.get("sentence"))+"'>复制</button></article>" for index, item in enumerate(group.get("items", []), 1))
            phrases.append("<details class='phrase-chapter' open><summary><b>"+esc(group.get("title"))+"</b><span>"+str(len(group.get("items", [])))+" 句</span><i aria-hidden='true'>＋</i></summary><div class='phrase-items'>"+rows+"</div></details>")
        if not vocab and not phrases: return ""
        return "<details class='language-edition'"+open_attr+"><summary><span><small>LANGUAGE</small><b>"+esc(label)+"</b></span><i aria-hidden='true'>＋</i></summary><div class='language-body'><div class='language-kicker'>高频关键词</div><div class='vocab-grid'>"+"".join(vocab)+"</div><div class='language-kicker'>现场高频句</div><div class='phrase-groups'>"+"".join(phrases)+"</div></div></details>"
    local_language = language_set(language_model.get("keyword_groups", []), language_model.get("phrase_groups", []), language_model.get("local_label", "当地语言"), " open")
    english_language = language_set(language_model.get("english_keyword_groups", []), language_model.get("english_phrase_groups", []), "英语备用", " open")
    language_html = "<section class='module language' id='language'><h2>语言</h2><p class='language-intro'>先用法语开场；需要时直接切换到简洁英语。每句可一键复制。</p>"+local_language+english_language+"</section>" if local_language or english_language else ""
    notes_groups = []
    for index, group in enumerate(profile.get("module_groups", {}).get("travel_notes", [])):
        items = group.get("items", [])
        if not items: continue
        item_cards = "".join("<article><h3>"+esc(item.get("title"))+"</h3><p>"+esc(item.get("note"))+"</p></article>" for item in items)
        open_attr = " open"
        notes_groups.append("<details class='notes-chapter'"+open_attr+"><summary><span><small>"+esc(group.get("kicker") or "LOCAL NOTES")+"</small><b>"+esc(group.get("title"))+"</b><em>"+esc(group.get("summary"))+"</em></span><i aria-hidden='true'>＋</i></summary><div class='notes-grid'>"+item_cards+"</div></details>")
    notes_html = "<section class='module notes' id='notes'><h2>注意事项</h2><p class='notes-intro'>把真正会影响旅途判断的事项，按场景集中在这里。</p>"+"".join(notes_groups)+"</section>" if notes_groups else ""
    pending = []
    if profile.get("transport", {}).get("status") != "confirmed": pending.append("往返交通")
    if any(stay.get("status") != "confirmed" for stay in profile.get("stays", [])): pending.append("住宿")
    status_html = "<aside class='status-banner'><b>行前待确认</b><span>"+"、".join(pending)+"尚未确定；确认后会同步更新行程接驳和每日出发点。</span><a href='#preparation'>查看准备清单</a></aside>" if pending else ""
    entries = [("01", "itinerary", "每日行程", "路线、地图、交通与停留"), ("02", "food", "餐饮指南", "当地小食与餐厅"), ("03", "experiences", "当地特色体验", "可选的当地体验"), ("04", "shopping", "购物", "按路线顺路购买"), ("05", "preparation", "准备清单", "预约、证件与行前确认"), ("06", "language", "语言", "高频关键词与现场表达"), ("07", "notes", "注意事项", "天气、交通、安全与支付")]
    directory_cards = "".join("<a href='#"+anchor+"'><b>"+number+"</b><span>"+label+"</span><em>"+description+"</em></a>" for number, anchor, label, description in entries)
    directory = "<section class='contents' aria-label='旅行手册目录'><div class='contents-head'><p>CONTENTS · 随时跳转</p><h2>从这里，翻到旅途的任意一页。</h2></div><div class='contents-grid'>"+directory_cards+"</div></section>"
    prep = profile.get("handbook_preparation", {})
    confirmations = prep.get("confirmations", [])
    packing = prep.get("packing", [])
    storage_prefix = "travel-handbook:"+str(profile.get("destination", "trip"))
    def checklist(kind, index, heading, subtitle, items):
        rows = []
        for item_index, item in enumerate(items, 1):
            title_text = item.get("title", "") if isinstance(item, dict) else str(item)
            timing = item.get("timing", "") if isinstance(item, dict) else ""
            rows.append("<li><label><input type='checkbox'><span>"+str(item_index).zfill(2)+"</span><div><b>"+esc(title_text)+"</b>"+("<em>"+esc(timing)+"</em>" if timing else "")+"</div></label></li>")
        return "<section class='checklist-group' data-checklist='"+kind+"' data-storage-key='"+esc(storage_prefix+":"+kind)+"'><header><span>"+index+"</span><div><h3>"+heading+"</h3><p>"+subtitle+"</p></div><b class='check-progress'>0 / "+str(len(items))+(" 已确认" if kind == "confirmations" else " 已准备")+"</b></header><div class='progress-track'><i></i></div><ol>"+"".join(rows)+"</ol></section>"
    preparation_html = "<section class='module preparation' id='preparation'><h2>准备清单</h2><p class='preparation-intro'>把预约、资料和行李集中在同一页完成。勾选进度会自动保存在这台设备上。</p>"+checklist("confirmations", "01", "预约与确认", "按出发时间倒排，先锁定真正影响行程的事项。", confirmations)+checklist("packing", "02", "行李与随身物品", "出发前逐项打包，避免把临时购买变成行程负担。", packing)+"</section>"
    adjust_days = []
    for index, day in enumerate(profile.get("itinerary", []), 1):
        adjust_stops = []
        for stop in day.get("stops", []):
            place = places.get(str(stop.get("place_id")))
            if place: adjust_stops.append({"place_id": place.get("place_id"), "name": place.get("name")})
        adjust_days.append({"index": index, "date": day.get("date"), "theme": day.get("theme"), "stops": adjust_stops})
    adjust_data = json.dumps(adjust_days, ensure_ascii=False).replace("</", "<\\/")
    adjust_html = "<div class='adjust-modal' id='adjust-modal' hidden><section class='adjust-dialog' role='dialog' aria-modal='true' aria-labelledby='adjust-title'><button type='button' class='adjust-close' id='close-adjust-modal' aria-label='关闭调整行程'>×</button><div><p class='adjust-kicker'>ADJUST ITINERARY</p><h2 id='adjust-title'>调整每日行程</h2><p>在这里试着移动或移除已有地点，再补充新增需求。页面会生成一段修改提示词；发送给 AI 后，由 Skill 重新研究、核验并生成新版本。</p></div><div class='adjust-controls'><label>选择日期<select id='adjust-day-select'></select></label><div id='adjust-stop-list' class='adjust-stop-list'></div><label>新增地点或其他调整<textarea id='adjust-request' rows='4' placeholder='例如：Day 3 想加入一家书店；不想去玛黑区；晚餐改为轻松一点。'></textarea></label><button type='button' id='generate-adjust-prompt'>生成修改提示词</button><label>发送给 AI 的提示词<textarea id='adjust-prompt' rows='10' readonly placeholder='点击上方按钮生成'></textarea></label><div class='adjust-actions'><button type='button' id='copy-adjust-prompt' class='secondary'>复制提示词</button><button type='button' id='cancel-adjust-edit' class='secondary'>取消编辑</button></div></div></section></div>"
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
    body = "<header class='hero-cover'"+cover_style+"><div class='hero-cover__shade'></div><div class='hero-cover__content'><p class='hero-cover__kicker'>TRAVEL HANDBOOK · "+esc(trip.get("start_date"))+"—"+esc(trip.get("end_date"))+"</p><h1>"+esc(title)+"</h1><p class='hero-cover__meta'>"+esc(trip.get("travelers"))+" · "+esc(trip.get("rhythm"))+" · "+esc("、".join(trip.get("interests", [])))+"</p>"+logistics_html+"<div class='hero-cover__actions'><a class='download' href='travel-handbook.pdf' download>一键下载 PDF</a><button type='button' class='adjust-link' id='open-adjust-modal'>调整行程</button></div></div></header>"+status_html+directory+"<section id='itinerary'>"+"".join(days)+"</section>"+food_html+experiences_html+shopping_html+preparation_html+language_html+notes_html+"<footer>来源与核验日期保留在各地点卡片中。</footer>"
    extras = "summary.head{cursor:pointer;list-style:none;align-items:start}summary.head::-webkit-details-marker{display:none}.chevron{margin-left:auto;font-style:normal;font-size:29px;line-height:1;transition:transform .2s}.day[open] .chevron{transform:rotate(90deg)}.contents{margin:18px 0 26px;padding:42px;background:#07392f;color:#fff8ec;border-radius:0}.contents-head{max-width:620px;margin-bottom:76px}.contents-head p{color:#edb65c;letter-spacing:.16em;font-size:12px;font-weight:700}.contents-head h2{color:#fff8ec;font-size:clamp(42px,6vw,74px);line-height:1.12;max-width:500px}.contents-grid{border-top:1px solid #789489}.contents-grid a{position:relative;display:grid;grid-template-columns:110px 1fr 24px;gap:0 22px;align-items:center;min-height:142px;padding:28px 4px;border-bottom:1px solid #507368;color:#fff8ec;text-decoration:none}.contents-grid a:hover{background:#104b3f}.contents-grid b{grid-row:span 2;color:#edb65c;font-family:Georgia,serif;font-size:32px}.contents-grid span{font-family:Georgia,'Songti SC',serif;font-size:34px}.contents-grid em{color:#b7c9c1;font-size:15px;font-style:normal}.contents-grid i{grid-row:span 2;color:#edb65c;font-style:normal;font-size:20px}.map img{width:min(100%,430px);height:300px;object-fit:contain;margin:16px auto;background:#f4efe5;border-radius:14px}.day-map-action{display:flex;gap:10px;align-items:center;margin:0 0 14px}.day-map-action a{font-weight:700}.day-map-action span{color:#766d63;font-size:13px}.status-banner{display:flex;align-items:center;gap:12px;margin:18px 0;padding:14px 16px;border:1px solid #dfba85;background:#fff3dd;border-radius:14px}.status-banner b{color:#9d493e}.status-banner a{margin-left:auto;white-space:nowrap}.logistics-summary{margin:14px 0 0;max-width:900px;color:#f4e3cf;font-size:14px}.logistics-summary p{margin:4px 0;letter-spacing:0}.transport-card{display:flex;align-items:center;gap:12px;margin:2px 12px;padding:10px 14px;border-left:2px dashed #bc9a76;color:#685445}.transport-card span{font-size:20px;color:#a94e42}.transport-card em{margin-left:auto;font-style:normal;font-size:13px;white-space:nowrap}.day-empty-note{padding:0 12px;color:#766d63}@media(max-width:700px){.contents{padding:30px 20px}.contents-head{margin-bottom:44px}.contents-head h2{font-size:48px}.contents-grid a{grid-template-columns:58px 1fr 18px;gap:0 12px;min-height:112px;padding:20px 0}.contents-grid b{font-size:25px}.contents-grid span{font-size:27px}.contents-grid em{font-size:13px}.map img{width:100%;height:260px}.day-map-action{align-items:flex-start;flex-direction:column;gap:1px}.status-banner{align-items:flex-start;flex-wrap:wrap}.status-banner a{margin-left:0}.transport-card{align-items:flex-start;flex-wrap:wrap}.transport-card em{margin-left:32px;white-space:normal}.logistics-summary{font-size:12px}}"
    directory_overrides = ".contents{margin:18px 0 26px;padding:28px 30px;background:#efe4d6;color:#293c34;border:1px solid #dfcdb8;border-radius:18px}.contents-head{max-width:none;margin-bottom:24px}.contents-head p{color:#a94e42;letter-spacing:.14em;font-size:12px;font-weight:700}.contents-head h2{color:#293c34;font-size:clamp(34px,4vw,48px);line-height:1.2}.contents-grid{display:grid;grid-template-columns:repeat(2,1fr);border-top:1px solid #cdbba5}.contents-grid a{display:grid;grid-template-columns:50px 1fr 20px;gap:0 12px;align-items:center;min-height:84px;padding:16px 10px;background:transparent;border-bottom:1px solid #cdbba5;color:#293c34;text-decoration:none;border-radius:0}.contents-grid a:nth-child(odd){border-right:1px solid #cdbba5;padding-right:20px}.contents-grid a:nth-child(even){padding-left:20px}.contents-grid a:hover{background:#e5d5c1}.contents-grid b{grid-row:span 2;color:#a94e42;font-family:Georgia,serif;font-size:24px}.contents-grid span{font-family:Georgia,'Songti SC',serif;font-size:25px}.contents-grid em{color:#766d63;font-size:13px;font-style:normal}.contents-grid i{grid-row:span 2;color:#a94e42;font-style:normal;font-size:18px}@media(max-width:700px){.contents{padding:24px 18px}.contents-grid{grid-template-columns:1fr}.contents-grid a:nth-child(odd){border-right:0;padding-right:0}.contents-grid a:nth-child(even){padding-left:0}.contents-grid a{min-height:76px;padding:14px 0}.contents-grid span{font-size:23px}}"
    place_overrides = ".stop-facts{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.stop-facts span{padding:4px 7px;background:#f1e2cf;border-radius:6px;color:#685445;font-size:12px}"
    directory_compact = ".contents{padding:22px 24px}.contents-head{margin-bottom:16px}.contents-head h2{font-size:clamp(28px,3.4vw,38px)}.contents-grid{grid-template-columns:repeat(3,1fr)}.contents-grid a{grid-template-columns:34px 1fr 16px;gap:0 8px;min-height:66px;padding:11px 8px}.contents-grid b{font-size:20px}.contents-grid span{font-size:21px}.contents-grid em{font-size:11px}.contents-grid i{font-size:15px}@media(max-width:850px){.contents-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:700px){.contents{padding:20px 16px}.contents-grid{grid-template-columns:1fr}.contents-grid a{min-height:70px;padding:12px 0}.contents-grid span{font-size:22px}}"
    directory_single_column = ".contents-grid{grid-template-columns:1fr}.contents-grid a{grid-template-columns:110px 1fr;gap:0 12px;min-height:72px;padding:10px 4px}.contents-grid a:nth-child(odd),.contents-grid a:nth-child(even){border-right:0;padding-left:4px;padding-right:4px}.contents-grid b{font-size:22px}.contents-grid span{font-size:25px;line-height:1.15}.contents-grid em{font-size:13px;line-height:1.3}.contents-grid i{display:none}.contents-head{margin-bottom:12px}.contents-head h2{font-size:32px}@media(max-width:700px){.contents-grid a{grid-template-columns:64px 1fr;min-height:66px;padding:9px 0}.contents-grid b{font-size:20px}.contents-grid span{font-size:23px}.contents-grid em{font-size:12px}.contents-head h2{font-size:28px}}"
    preparation_styles = ".preparation{padding:30px}.preparation-intro{margin:-4px 0 26px;color:#766d63}.checklist-group{margin-top:26px;padding-top:22px;border-top:1px solid #dfcdb8}.checklist-group header{display:grid;grid-template-columns:54px 1fr auto;gap:12px;align-items:center}.checklist-group header>span{color:#a94e42;font:28px Georgia,serif}.checklist-group h3{margin:0;font-size:25px}.checklist-group header p{margin:2px 0 0;color:#766d63;font-size:13px}.check-progress{font-size:13px;color:#685445}.progress-track{height:7px;margin:14px 0 18px;background:#ebdfcf;border-radius:99px;overflow:hidden}.progress-track i{display:block;width:0;height:100%;background:#a94e42;transition:width .2s}.checklist-group ol{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 18px;margin:0;padding:0;list-style:none}.checklist-group li{border-bottom:1px solid #eadfce}.checklist-group label{display:grid;grid-template-columns:22px 30px 1fr;gap:8px;align-items:start;padding:10px 0;cursor:pointer}.checklist-group input{margin-top:4px;accent-color:#a94e42}.checklist-group label>span{color:#a94e42;font:14px Georgia,serif}.checklist-group label b{display:block;font-size:14px}.checklist-group label em{display:block;color:#766d63;margin-top:2px;font-size:12px;font-style:normal}.checklist-group li.is-checked b{text-decoration:line-through;color:#8e8377}@media(max-width:700px){.preparation{padding:24px 18px}.checklist-group header{grid-template-columns:42px 1fr}.check-progress{grid-column:2}.checklist-group ol{grid-template-columns:1fr}}"
    food_styles = ".food-chapter{margin-top:14px;background:#fbf5eb;border:1px solid #e6d8c5}.food-chapter summary{display:flex;justify-content:space-between;cursor:pointer;padding:16px 18px;font:22px Georgia,'Songti SC',serif;list-style:none}.food-chapter summary::-webkit-details-marker{display:none}.food-chapter summary span{font:13px -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;color:#766d63}.restaurant-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;padding:0 18px 18px}.restaurant-card{overflow:hidden;background:#fffdf8;border:1px solid #e4d4c0}.restaurant-card img{display:block;width:100%;height:200px;object-fit:cover}.restaurant-card>div{padding:16px}.restaurant-card h3{margin:4px 0 10px;font-size:27px}.restaurant-card p{margin:6px 0;font-size:13px}.restaurant-meta{color:#a94e42;font-weight:700}.restaurant-foot{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;padding-top:12px;border-top:1px solid #eadfce}.restaurant-foot span{margin-right:auto;font-weight:700}.snack-grid,.term-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:0 18px 18px}.snack-card,.term-card{padding:14px;background:#fffdf8;border-left:3px solid #d5a16d}.snack-card h3,.term-card b{margin:0;color:#293c34;font:22px Georgia,'Songti SC',serif}.snack-card small{color:#a94e42}.snack-card p,.term-card p{margin:6px 0;font-size:13px}.term-card{display:grid;grid-template-columns:1fr 1fr;gap:4px 10px}.term-card span{color:#a94e42;font-weight:700}.term-card p{grid-column:span 2;color:#766d63}@media(max-width:700px){.restaurant-grid,.snack-grid,.term-grid{grid-template-columns:1fr;padding-left:12px;padding-right:12px}.restaurant-card img{height:220px}.food-chapter summary{font-size:20px;padding:14px}.term-card{grid-template-columns:1fr}}"
    experience_styles = ".experiences-intro{margin:-4px 0 20px;color:#766d63}.experience-chapter{margin-top:14px;background:#fbf5eb;border:1px solid #e6d8c5}.experience-chapter summary{display:flex;align-items:center;justify-content:space-between;gap:16px;cursor:pointer;padding:15px 18px;list-style:none}.experience-chapter summary::-webkit-details-marker{display:none}.experience-chapter summary b{display:block;font:24px Georgia,'Songti SC',serif}.experience-chapter summary small{display:block;margin-top:2px;color:#766d63;font-size:13px}.experience-chapter summary i{color:#a94e42;font-style:normal;font-size:22px;transition:transform .2s}.experience-chapter[open] summary i{transform:rotate(45deg)}.experience-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding:0 18px 18px}.experience-card{overflow:hidden;background:#fffdf8;border:1px solid #e4d4c0}.experience-card>img,.experience-image{display:block;width:100%;height:210px;object-fit:cover;background:#eadfce}.experience-image.empty{display:flex;align-items:center;justify-content:center;color:#85796c;font-size:13px}.experience-copy{padding:16px}.experience-copy h3{margin:3px 0 9px;font-size:27px}.experience-copy p{margin:6px 0;font-size:13px}.experience-meta{color:#a94e42;font-weight:700}.experience-schedule{color:#685445}.experience-fit{padding:9px 10px;background:#f3e8d8}.experience-facts{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.experience-facts span{padding:4px 7px;background:#f1e2cf;border-radius:6px;color:#685445;font-size:12px}.experience-foot{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;padding-top:12px;border-top:1px solid #eadfce;font-size:13px}@media(max-width:700px){.experience-grid{grid-template-columns:1fr;padding-left:12px;padding-right:12px}.experience-card>img,.experience-image{height:220px}.experience-chapter summary{padding:14px}.experience-chapter summary b{font-size:21px}}"
    shopping_styles = ".shopping-intro{margin:-4px 0 20px;color:#766d63}.shopping-chapter{margin-top:14px;background:#fbf5eb;border:1px solid #e6d8c5}.shopping-chapter summary{display:flex;align-items:center;justify-content:space-between;gap:16px;cursor:pointer;padding:15px 18px;list-style:none}.shopping-chapter summary::-webkit-details-marker{display:none}.shopping-chapter summary b{display:block;font:24px Georgia,'Songti SC',serif}.shopping-chapter summary small{display:block;margin-top:2px;color:#766d63;font-size:13px}.shopping-chapter summary i{color:#a94e42;font-style:normal;font-size:22px;transition:transform .2s}.shopping-chapter[open] summary i{transform:rotate(45deg)}.shopping-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;padding:0 18px 18px}.shopping-card{overflow:hidden;background:#fffdf8;border:1px solid #e4d4c0}.shopping-card>img,.shopping-image{display:block;width:100%;height:210px;object-fit:cover;background:#eadfce}.shopping-image.empty{display:flex;align-items:center;justify-content:center;color:#85796c;font-size:13px}.shopping-copy{padding:16px}.shopping-copy h3{margin:3px 0 9px;font-size:27px}.shopping-copy p{margin:6px 0;font-size:13px}.shopping-meta,.goodie-meta{color:#a94e42;font-weight:700}.shopping-schedule{color:#685445}.shopping-tip{padding:9px 10px;background:#f3e8d8}.shopping-facts{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}.shopping-facts span{padding:4px 7px;background:#f1e2cf;border-radius:6px;color:#685445;font-size:12px}.shopping-foot{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px;padding-top:12px;border-top:1px solid #eadfce;font-size:13px}.goodie-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding:0 18px 18px}.goodie-card{padding:15px;background:#fffdf8;border-left:3px solid #d5a16d}.goodie-card h3{margin:3px 0 8px;font-size:23px}.goodie-card p{margin:6px 0;font-size:13px}.goodie-card small{display:block;margin-top:10px;color:#766d63}@media(max-width:700px){.shopping-grid,.goodie-grid{grid-template-columns:1fr;padding-left:12px;padding-right:12px}.shopping-card>img,.shopping-image{height:220px}.shopping-chapter summary{padding:14px}.shopping-chapter summary b{font-size:21px}}"
    notes_styles = ".notes-intro{margin:-4px 0 20px;color:#766d63}.notes-chapter{margin-top:12px;background:#fbf5eb;border:1px solid #e6d8c5}.notes-chapter summary{display:flex;align-items:center;justify-content:space-between;gap:16px;cursor:pointer;padding:15px 18px;list-style:none}.notes-chapter summary::-webkit-details-marker{display:none}.notes-chapter summary small,.notes-chapter summary b,.notes-chapter summary em{display:block}.notes-chapter summary small{color:#a94e42;font-size:11px;letter-spacing:.12em;font-weight:700}.notes-chapter summary b{font:24px Georgia,'Songti SC',serif}.notes-chapter summary em{margin-top:2px;color:#766d63;font-size:13px;font-style:normal}.notes-chapter summary i{color:#a94e42;font-style:normal;font-size:22px;transition:transform .2s}.notes-chapter[open] summary i{transform:rotate(45deg)}.notes-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:#e6d8c5;border-top:1px solid #e6d8c5}.notes-grid article{padding:15px 18px;background:#fffdf8}.notes-grid h3{margin:0 0 5px;font-size:21px}.notes-grid p{margin:0;font-size:13px;color:#5f574d}@media(max-width:700px){.notes-grid{grid-template-columns:1fr}.notes-chapter summary{padding:14px}.notes-chapter summary b{font-size:21px}}"
    language_styles = ".language-intro{margin:-4px 0 20px;color:#766d63}.language-edition{margin-top:14px;background:#fbf5eb;border:1px solid #e6d8c5}.language-edition>summary{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;cursor:pointer;list-style:none}.language-edition>summary::-webkit-details-marker,.vocab-chapter summary::-webkit-details-marker,.phrase-chapter summary::-webkit-details-marker{display:none}.language-edition small,.language-edition b{display:block}.language-edition small{color:#a94e42;font-size:11px;letter-spacing:.12em}.language-edition b{font:24px Georgia,'Songti SC',serif}.language-edition>summary>i,.vocab-chapter summary i,.phrase-chapter summary i{color:#a94e42;font-style:normal;font-size:22px;transition:transform .2s}.language-edition[open]>summary>i,.vocab-chapter[open] summary i,.phrase-chapter[open] summary i{transform:rotate(45deg)}.language-body{padding:0 18px 18px}.language-kicker{margin:16px 0 8px;color:#766d63;font-size:12px;font-weight:700;letter-spacing:.1em}.vocab-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.vocab-chapter,.phrase-chapter{border:1px solid #e6d8c5;background:#fffdf8}.vocab-chapter summary,.phrase-chapter summary{display:flex;align-items:center;gap:10px;padding:12px;cursor:pointer;list-style:none}.vocab-chapter summary b,.phrase-chapter summary b{font-size:18px}.vocab-chapter summary span,.phrase-chapter summary span{margin-left:auto;color:#766d63;font-size:12px}.vocab-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-top:1px solid #e6d8c5}.vocab-items article{padding:11px;border-right:1px solid #e6d8c5;border-bottom:1px solid #e6d8c5}.vocab-items b,.vocab-items small,.vocab-items span{display:block}.vocab-items b{font-size:16px}.vocab-items small{color:#766d63}.vocab-items span{color:#a94e42;font-size:13px}.phrase-groups{display:grid;gap:10px}.phrase-items{border-top:1px solid #e6d8c5}.phrase-items article{display:grid;grid-template-columns:30px 1fr auto;gap:10px;align-items:start;padding:12px;border-bottom:1px solid #e6d8c5}.phrase-items article>span{color:#a94e42;font:15px Georgia,serif}.phrase-items b,.phrase-items small,.phrase-items em{display:block}.phrase-items b{font-size:15px}.phrase-items small{color:#766d63}.phrase-items em{color:#685445;font-size:13px;font-style:normal}.copy-phrase{border:1px solid #d5a16d;background:#fffdf8;color:#9d493e;border-radius:99px;padding:4px 10px;cursor:pointer;font-size:12px}@media(max-width:700px){.language-body{padding-left:12px;padding-right:12px}.vocab-grid{grid-template-columns:1fr}.vocab-items{grid-template-columns:1fr}.language-edition>summary{padding:14px}.language-edition b{font-size:21px}.phrase-items article{grid-template-columns:26px 1fr}.copy-phrase{grid-column:2;justify-self:start}}"
    adjust_styles = ".adjust-link{display:inline-block;margin:18px 0 0 10px;color:#fff;border:1px solid rgba(255,255,255,.55);padding:10px 16px;border-radius:99px;text-decoration:none}.adjust-itinerary{margin:22px 0;padding:28px;background:#293c34;color:#fff8ec;border-radius:22px}.adjust-itinerary h2{margin:4px 0 8px}.adjust-kicker{margin:0;color:#edb65c;letter-spacing:.13em;font-size:12px;font-weight:700}.adjust-itinerary>div>p:not(.adjust-kicker){margin:0;color:#d3dfd8;max-width:780px}.adjust-controls{display:grid;gap:14px;margin-top:20px}.adjust-controls label{display:grid;gap:6px;color:#fff8ec;font-weight:700}.adjust-controls select,.adjust-controls textarea{width:100%;border:1px solid #6d8c80;border-radius:10px;padding:10px;background:#fffdf8;color:#29251f;font:14px -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;line-height:1.55}.adjust-controls button{justify-self:start;border:0;border-radius:99px;padding:10px 16px;background:#edb65c;color:#293c34;font-weight:700;cursor:pointer}.adjust-controls button.secondary{background:transparent;color:#fff8ec;border:1px solid #7e9c90}.adjust-stop-list{display:grid;gap:8px}.adjust-stop-row{display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center;padding:10px 12px;background:#355046;border:1px solid #577568;border-radius:10px}.adjust-stop-row b{font-size:14px}.adjust-stop-row button{padding:4px 9px;background:#47675b;color:#fff8ec;border:0;border-radius:7px}.adjust-stop-row button.remove{background:#754c42}@media(max-width:700px){.adjust-itinerary{padding:22px 18px}.adjust-stop-row{grid-template-columns:1fr auto auto}.adjust-stop-row b{grid-column:span 3}.adjust-link{margin-left:6px}}"
    adjust_modal_styles = ".adjust-link{font:inherit;cursor:pointer;background:transparent}.adjust-modal[hidden]{display:none}.adjust-modal{position:fixed;z-index:20;inset:0;display:grid;place-items:center;padding:20px;background:rgba(24,32,29,.62);overflow:auto}.adjust-dialog{position:relative;width:min(760px,100%);max-height:calc(100vh - 40px);overflow:auto;padding:28px;background:#293c34;color:#fff8ec;border:1px solid #638276;border-radius:22px;box-shadow:0 20px 70px rgba(0,0,0,.35)}.adjust-dialog h2{margin:4px 0 8px}.adjust-dialog>div>p:not(.adjust-kicker){margin:0;color:#d3dfd8;max-width:680px}.adjust-close{position:absolute;right:16px;top:14px;border:0;background:transparent;color:#fff8ec;font-size:32px;line-height:1;cursor:pointer}.adjust-actions{display:flex;gap:10px;flex-wrap:wrap}@media(max-width:700px){.adjust-modal{padding:8px}.adjust-dialog{max-height:calc(100vh - 16px);padding:24px 18px;border-radius:16px}.adjust-link{margin-left:6px}}"
    editorial_styles = ":root{--editorial-deep:#092f2b;--editorial-forest:#17483e;--editorial-sand:#f5efe4;--editorial-gold:#e7b369;--editorial-ink:#22322c}body{background:var(--editorial-sand);color:var(--editorial-ink)}main{max-width:1180px;padding:28px}.hero-cover{isolation:isolate;position:relative;min-height:520px;display:flex;align-items:end;overflow:hidden;margin-bottom:28px;padding:0;border-radius:0;background-color:var(--editorial-deep);background-image:var(--cover-image),linear-gradient(135deg,#082c28,#245849);background-position:center;background-size:cover}.hero-cover__shade{position:absolute;inset:0;z-index:-1;background:linear-gradient(90deg,rgba(5,29,26,.94) 0%,rgba(8,38,33,.72) 48%,rgba(8,38,33,.28) 100%)}.hero-cover__content{width:min(780px,100%);padding:68px 54px;color:#fff8ec}.hero-cover__kicker{margin:0 0 16px;color:var(--editorial-gold);font:700 11px/1.3 Arial,sans-serif;letter-spacing:.2em}.hero-cover h1{max-width:620px;margin:0 0 18px;font:500 clamp(62px,9vw,118px)/.94 Georgia,'Songti SC',serif;letter-spacing:-.06em}.hero-cover__meta{color:#dfebe4;font-size:16px}.hero-cover .logistics-summary{color:#f5ead8;max-width:650px}.hero-cover__actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:24px}.hero-cover .download,.hero-cover .adjust-link{margin:0;padding:11px 17px;border:1px solid rgba(255,255,255,.5);border-radius:99px}.hero-cover .download{background:var(--editorial-gold);color:#17342e}.hero-cover .adjust-link{color:#fff8ec}.contents{background:#163f36;border:0;border-radius:0}.contents-head h2{color:#fff8ec}.contents-head p{color:var(--editorial-gold)}.contents-grid{border-top-color:rgba(244,235,215,.48)}.contents-grid a{color:#fff8ec;border-bottom-color:rgba(244,235,215,.3)}.contents-grid em{color:#c5d8cf}.contents-grid b{color:var(--editorial-gold)}.day{border:0;border-radius:0;border-left:4px solid #cda36c;box-shadow:0 12px 32px rgba(34,50,44,.05)}.day[open]{border-left-color:#a85b4b}.day .head>span{font:italic 500 24px Georgia,serif;color:#a85b4b}.day h2,.module>h2{letter-spacing:-.04em}.module{border:0;border-radius:0;box-shadow:0 12px 32px rgba(34,50,44,.04)}.module>h2{padding-bottom:14px;border-bottom:1px solid #dfd2bf}.food-chapter,.experience-chapter,.shopping-chapter,.notes-chapter,.language-edition{border-radius:0}.stop{border-left-width:2px}.stop-image,.restaurant-card,.experience-card,.shopping-card{border-radius:0}.day-map-action a{display:inline-flex;align-items:center;padding:6px 10px;border:1px solid #d5a16d;border-radius:99px;text-decoration:none}.transport-card{border-left-color:#a85b4b}.adjust-modal{backdrop-filter:blur(5px)}@media(max-width:700px){main{padding:14px}.hero-cover{min-height:460px;margin:0 -14px 20px}.hero-cover__content{padding:48px 26px}.hero-cover h1{font-size:64px}.hero-cover__meta{font-size:14px}.contents{margin-left:0;margin-right:0}}"
    design_system = ":root{--handbook-bg:#f4eee5;--handbook-surface:#fffaf3;--handbook-ink:#263b40;--handbook-muted:#6d7778;--handbook-primary:#1f6678;--handbook-accent:#b7654f;--handbook-gold:#c9954b;--handbook-line:#dfd2c4}body{background:var(--handbook-bg);color:var(--handbook-ink)}a{color:var(--handbook-primary)}.hero-cover{background-color:var(--handbook-primary);background-image:var(--cover-image),linear-gradient(135deg,#173f4c,#267487)}.hero-cover__shade{background:linear-gradient(90deg,rgba(23,63,76,.94),rgba(31,102,120,.58),rgba(31,102,120,.2))}.hero-cover__kicker,.contents-head p{color:var(--handbook-gold)}.contents{background:var(--handbook-primary)}.contents-grid a{border-bottom-color:#ffffff4d}.contents-grid b{color:var(--handbook-gold)}.day,.module{background:var(--handbook-surface);border-color:var(--handbook-line)}.day .head>span,.head>span{color:var(--handbook-accent)}.stop,.module-card{background:#faf2e8;border-left-color:#d4a15f}.stop-image.empty{background:#eee3d7}.status-banner{border-color:#d8b77d;background:#fff2db}.status-banner b,.restaurant-meta,.experience-meta,.shopping-meta,.goodie-meta{color:var(--handbook-accent)}.transport-card{border-left-color:var(--handbook-accent)}.preparation,.food-chapter,.experience-chapter,.shopping-chapter,.notes-chapter,.language-edition{background:#faf2e8;border-color:var(--handbook-line)}.checklist-group,.restaurant-card,.experience-card,.shopping-card,.goodie-card,.notes-grid article{border-color:var(--handbook-line)}.checklist-group input,.progress-track i{accent-color:var(--handbook-primary)}.progress-track i{background:var(--handbook-primary)}.adjust-controls button{background:var(--handbook-gold)}"
    checklist_script = "<script>document.querySelectorAll('[data-checklist]').forEach(function(group){var key=group.dataset.storageKey,inputs=[].slice.call(group.querySelectorAll('input')),label=group.querySelector('.check-progress'),bar=group.querySelector('.progress-track i'),suffix=group.dataset.checklist==='confirmations'?' 已确认':' 已准备',saved=[];try{saved=JSON.parse(localStorage.getItem(key)||'[]')}catch(e){}inputs.forEach(function(input,index){input.checked=saved.indexOf(index)>-1;input.closest('li').classList.toggle('is-checked',input.checked);input.addEventListener('change',update)});function update(){var checked=[];inputs.forEach(function(input,index){if(input.checked)checked.push(index);input.closest('li').classList.toggle('is-checked',input.checked)});try{localStorage.setItem(key,JSON.stringify(checked))}catch(e){}label.textContent=checked.length+' / '+inputs.length+suffix;bar.style.width=(inputs.length?checked.length/inputs.length*100:0)+'%'}update()});document.querySelectorAll('.copy-phrase').forEach(function(button){button.addEventListener('click',function(){var text=button.dataset.copy,navigatorCopy=navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(text):Promise.reject();navigatorCopy.then(function(){button.textContent='已复制';setTimeout(function(){button.textContent='复制'},1200)}).catch(function(){button.textContent='请长按复制'})})})</script>"
    adjust_script = "<script>const adjustDays="+adjust_data+";let adjustState=adjustDays.map(function(day){return {index:day.index,date:day.date,theme:day.theme,stops:day.stops.slice()}});const daySelect=document.getElementById('adjust-day-select'),stopList=document.getElementById('adjust-stop-list'),requestInput=document.getElementById('adjust-request'),promptOutput=document.getElementById('adjust-prompt');function currentDay(){return adjustState[Number(daySelect.value)||0]}function renderAdjust(){if(!daySelect.options.length){adjustState.forEach(function(day,index){let option=document.createElement('option');option.value=index;option.textContent='Day '+day.index+' · '+day.date+' · '+day.theme;daySelect.appendChild(option)})}let day=currentDay();stopList.innerHTML='';if(!day.stops.length){stopList.textContent='当前未保留地点；请在下方说明希望新增或重排的地点。';return}day.stops.forEach(function(stop,index){let row=document.createElement('div');row.className='adjust-stop-row';row.innerHTML='<b>'+String(index+1).padStart(2,'0')+' · '+stop.name+'</b><button type=\"button\" data-action=\"up\" data-index=\"'+index+'\">上移</button><button type=\"button\" data-action=\"down\" data-index=\"'+index+'\">下移</button><button type=\"button\" class=\"remove\" data-action=\"remove\" data-index=\"'+index+'\">移除</button>';stopList.appendChild(row)})}daySelect.addEventListener('change',renderAdjust);stopList.addEventListener('click',function(event){let button=event.target.closest('button');if(!button)return;let day=currentDay(),index=Number(button.dataset.index),action=button.dataset.action;if(action==='up'&&index>0){let item=day.stops.splice(index,1)[0];day.stops.splice(index-1,0,item)}if(action==='down'&&index<day.stops.length-1){let item=day.stops.splice(index,1)[0];day.stops.splice(index+1,0,item)}if(action==='remove')day.stops.splice(index,1);renderAdjust()});document.getElementById('generate-adjust-prompt').addEventListener('click',function(){let day=currentDay(),stops=day.stops.length?day.stops.map(function(stop,index){return (index+1)+'. '+stop.name}).join('\\n'):'（当前地点已全部移除）',request=requestInput.value.trim()||'无额外说明。';promptOutput.value='请使用 Travel Handbook Skill 更新这份巴黎旅行手册。\\n\\n目标日期：Day '+day.index+' · '+day.date+' · '+day.theme+'\\n调整后的既有地点顺序：\\n'+stops+'\\n\\n新增地点或其他调整：\\n'+request+'\\n\\n要求：保留未提及日期和模块；对新增或调整的地点重新研究官方开放、预约、准确图片与来源；重新计算受影响路线、地图快照、地点间交通与每日全部地点地图链接。不要臆造动态信息。'});document.getElementById('copy-adjust-prompt').addEventListener('click',function(){if(!promptOutput.value)return;navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(promptOutput.value).then(function(){document.getElementById('copy-adjust-prompt').textContent='已复制';setTimeout(function(){document.getElementById('copy-adjust-prompt').textContent='复制提示词'},1200)}).catch(function(){promptOutput.select()}):promptOutput.select()});renderAdjust()</script>"
    adjust_modal_script = "<script>const adjustModal=document.getElementById('adjust-modal'),openAdjust=document.getElementById('open-adjust-modal'),closeAdjust=document.getElementById('close-adjust-modal'),cancelAdjust=document.getElementById('cancel-adjust-edit');function resetAdjust(){adjustState=adjustDays.map(function(day){return {index:day.index,date:day.date,theme:day.theme,stops:day.stops.slice()}});daySelect.innerHTML='';requestInput.value='';promptOutput.value='';renderAdjust()}function closeAdjustModal(){resetAdjust();adjustModal.hidden=true;openAdjust.focus()}openAdjust.addEventListener('click',function(){resetAdjust();adjustModal.hidden=false;closeAdjust.focus()});closeAdjust.addEventListener('click',closeAdjustModal);cancelAdjust.addEventListener('click',closeAdjustModal);adjustModal.addEventListener('click',function(event){if(event.target===adjustModal)closeAdjustModal()});document.addEventListener('keydown',function(event){if(event.key==='Escape'&&!adjustModal.hidden)closeAdjustModal()})</script>"
    structured_adjust_script = "<script>document.getElementById('generate-adjust-prompt').addEventListener('click',function(){let day=currentDay(),original=adjustDays[Number(daySelect.value)||0],originalIds=original.stops.map(function(stop){return stop.place_id}),draftIds=day.stops.map(function(stop){return stop.place_id}),operations=[],request=requestInput.value.trim();original.stops.forEach(function(stop){if(draftIds.indexOf(stop.place_id)<0)operations.push({type:'delete',place_id:stop.place_id,name:stop.name})});if(originalIds.join('|')!==draftIds.join('|'))operations.push({type:'reorder',ordered_place_ids:draftIds,ordered_place_names:day.stops.map(function(stop){return stop.name})});if(request)operations.push({type:'research_add_or_adjust',description:request});let payload={schema:'travel-handbook-change-request-v1',target_day:{number:day.index,date:day.date,theme:day.theme},operations:operations,freeform_request:request||null,current_itinerary_snapshot:{places:day.stops},preserve_unmentioned_content:true,required_rechecks:['受影响地点的官方开放与预约信息','路线、地点间交通与每日地图','准确地点图片与来源','动态事实的核验日期']};promptOutput.value='请使用 Travel Handbook Skill 按以下变更请求更新手册。未提及的日期与模块保持不变；新增或调整内容必须重新研究并核验。\\n\\n```json\\n'+JSON.stringify(payload,null,2)+'\\n```';})</script>"
    (out/"index.html").write_text("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>"+esc(title)+"旅行手册</title><style>"+css+extras+directory_overrides+place_overrides+directory_compact+directory_single_column+preparation_styles+food_styles+experience_styles+shopping_styles+notes_styles+language_styles+adjust_styles+adjust_modal_styles+editorial_styles+design_system+"</style></head><body><main>"+body+"</main>"+adjust_html+checklist_script+adjust_script+adjust_modal_script+structured_adjust_script+"</body></html>", encoding="utf-8")

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
    prep = profile.get("handbook_preparation", {})
    section("准备清单", "预约与确认、行李与随身物品")
    for heading, items in [("预约与确认", prep.get("confirmations", [])), ("行李与随身物品", prep.get("packing", []))]:
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
    profile, places = normalize(profile); render_html(profile, places, out); render_pdf(profile, places, out)
    print(f"PASS rendered {out/'index.html'} and {out/'travel-handbook.pdf'}")

if __name__ == "__main__": main()
