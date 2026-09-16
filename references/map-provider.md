# 地图与路线服务

地图是构建阶段生成的资产，不在旅行手册网页中实时渲染。

每一天生成一张带真实道路底图的路线截图、地点编号、地点之间的步行距离和预计分钟数，并为每个地点保留 Google Maps 或高德地图跳转链接。导航服务只保留这两种，不为页面增加更多地图入口。

路线服务统一返回：`geometry`、`distance_meters`、`duration_seconds`、`provider`、`checked_at`。静态截图优先使用有许可且适合目的地的路线服务；无密钥时使用 OpenStreetMap 数据和兼容的 OSRM 服务，并保留署名。静态截图服务与用户点击的导航服务可以不同。

`map_provider` 只允许 `google` 或 `amap`。未填写时，海外目的地默认 `google`，中国大陆目的地默认 `amap`；用户明确指定时以用户选择为准。Google Maps 使用地点检索和多点路线入口，高德使用地点标注和路线规划 URI。高德路线 URI 的途经点能力有限，多点日不能声称高德链接完整复现所有停靠点；此时以本地完整路线截图为准，并保留可执行的地点导航入口。

中国大陆目的地以 WGS84 作为研究数据的统一坐标源，生成高德链接或截图前转换为高德要求的 GCJ-02，禁止把未经转换的 GPS 坐标直接当作高德国内地图坐标。高德 URI 支持地点标注、搜索和路线规划；静态地图 API 支持图片、标注和折线覆盖物。

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
