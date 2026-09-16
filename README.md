# Travel Handbook Skill

一个用于研究并生成个性化旅行手册的 Codex skill。

## 使用方式

安装 skill 后，直接告诉 Agent 你想去哪里。信息不完整时，打开 `assets/intake-questionnaire/index.html` 填写目的地、日期、人数、节奏、预算和偏好，再把生成的提示词发回 Agent。

如果已经订了机票或酒店，可以在问卷的“其他说明”中填写航班号、酒店名称和入住日期。

完整需求也可以直接发送给 Agent，已提供的信息会跳过问卷。

## 输出

- `index.html`：旅行手册网页
- `destination-profile.json`：结构化旅行数据
- `map-snapshots/`：每日路线地图
- PDF：按需生成

## 示例

巴黎旅行手册示例位于 `docs/`，可作为 GitHub Pages 的静态网站根目录。
