# Travel handbook data model

最小数据结构：

```json
{
  "trip": {"destination": "Paris", "start_date": "2026-09-28", "end_date": "2026-10-04", "travelers": "情侣", "rhythm": "relaxed", "interests": ["美食", "拍照", "街区漫步"]},
  "places": [{"place_id": "louvre", "name": "卢浮宫", "type": "sight", "area": "巴黎中心", "address": "", "coordinates": {"latitude": 48.8606, "longitude": 2.3376}, "visit_minutes": 180, "reservation": "", "hours": "", "map_query": "Louvre Museum Paris", "source_url": "", "checked_at": "2026-09-13"}],
  "itinerary": [{"date": "2026-09-28", "theme": "", "reason": "", "place_ids": ["louvre"]}],
  "modules": {"food": [], "preparation": [], "notes": [], "shopping": [], "experiences": [], "language": []}
}
```

`place_id` 是跨模块的稳定引用。网页、地图快照和 PDF 都应从这份数据读取。

行程日期约束：`trip.start_date`、`trip.end_date` 和 `trip.days` 必须相互一致；`itinerary` 必须按连续日期覆盖整个旅行区间，不能遗漏抵达日或离境日。抵达/离境交通与住宿入住/退房日期应引用同一日历，不在页面模板中另写日期。

推荐补充字段：

```json
{
  "status": "confirmed | pending | candidate",
  "verification": {"checked_at": "2026-09-13", "next_check": "出发前 7 天", "action": "确认预约时段"},
  "budget": {"amount": "€18–25", "per": "人", "basis": "主菜 + 饮品估算", "source_url": ""},
  "image": {"file": "", "source_page": "", "media_class": "exact_entity | official | atmosphere", "checked_at": "2026-09-13"}
}
```

`budget` 没有可追溯金额或明确估算口径时不渲染。`image.media_class` 为 `atmosphere` 时必须在页面标注为示意图，不能作为实体实景使用。

体验实体使用 `type: "experience"`，除通用地点字段外，还应记录：`category`、`recommended_day` 或 `scheduled_label