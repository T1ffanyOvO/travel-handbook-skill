# 旅行手册输出约定

```text
output/
├── index.html
├── map-snapshots/
└── build-report.json
```

`travel-handbook.pdf` 是按需生成的同源附加文件，不是静态网页的前置条件。生成后，网页显示可用的下载入口；未生成时不得显示失效链接。

网页模块按以下顺序渲染：每日行程、餐饮指南、当地特色体验、购物、准备清单、语言、注意事项。每日行程、餐饮指南、准备清单、注意事项为核心；体验、购物和语言只在数据存在时显示。不存在独立的“景点指南”模块，景点详情属于每日行程地点卡。

网页和 PDF（如生成）必须使用相同的 `destination-profile.json`、地点引用和地图快照。完整规则见 [handbook-spec.md](handbook-spec.md)。
