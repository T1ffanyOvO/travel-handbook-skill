# 巴黎 6 日旅行手册示例

这是 Travel Handbook Skill 的完整示例，包含结构化旅行数据、HTML 手册、PDF、每日真实道路地图截图和来源信息。

- `destination-profile.json`：生成手册使用的唯一数据源
- `index.html`：可直接打开的静态旅行手册
- `travel-handbook.pdf`：与 HTML 使用同一份数据生成
- `map-snapshots/`：6 天真实道路路线截图
- `map-routes.json`：地图服务与路线核验记录

重新生成时，在 Skill 目录运行：

```text
python scripts/generate_real_maps.py examples/france-7d/destination-profile.json examples/france-7d/output
python scripts/render_handbook_v2.py examples/france-7d/destination-profile.json examples/france-7d/output
```
