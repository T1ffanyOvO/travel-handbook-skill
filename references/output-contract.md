# 旅行手册输出约定

```text
output/
├── index.html
├── map-snapshots/
└── build-report.json
```

PDF 不作为静态输出文件维护。网页只提供“一键打印/保存 PDF”按钮，由浏览器使用当前 DOM、图片、背景样式和清单勾选状态生成 PDF。

网页模块按以下顺序渲染：每日行程、餐饮指南、当地特色体验、购物、准备清单、语言、注意事项。每日行程、餐饮指南、准备清单、注意事项为核心；体验、购物和语言只在数据存在时显示。不存在独立的“景点指南”模块，景点详情属于每日行程地点卡。

网页打印内容直接来自当前 `index.html`，与 `destination-profile.json`、地点引用和地图快照保持同源。完整规则见 [handbook-spec.md](handbook-spec.md)。
