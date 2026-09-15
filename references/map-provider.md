# 地图与路线服务

地图是构建阶段生成的资产，不在旅行手册网页中实时渲染。

每一天生成一张带真实道路底图的路线截图、地点编号、地点之间的步行距离和预计分钟数，并为每个地点保留 Google Maps / Apple Maps 跳转链接。

路线服务统一返回：`geometry`、`distance_meters`、`duration_seconds`、`provider`、`checked_at`。有可用密钥时使用 Mapbox Directions + Static Images 或区域合适的官方地图服务；无密钥时使用 OpenStreetMap 数据和兼容的 OSRM 服务，并保留署名。

服务不可用时，保留地点坐标图和地图跳转链接，并明确标注“路线截图待生成”，不得把直线距离写成步行距离。

```json
{
  "from_place_id": "seine-new-bridge",
  "to_place_id": "saint-germain",
  "mode": "walking",
  "distance_meters": 1200,
  "duration_seconds": 1020,
  "snapshot_file": "map-snapshots/day-01-segment-01.png",
  "provider": "example-provider",
  "checked_at": "2026-09-13"
}
```
