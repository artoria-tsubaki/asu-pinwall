# ASU Pinwall

ASU Pinwall 是一个基于 `Vue 3 + Vite` 构建的虚拟歌手明透（ASU）主题展示站点。项目以“图钉墙”式首页为核心交互，将人物资料、代表作品、社交链接、最新动态、官方绘图、时间线和曲库内容整合到统一的视觉画布中，提供兼具策展感与沉浸感的浏览体验。

项目采用前端静态站点方案，配合本地脚本抓取和整理社交平台、曲库与图像等数据源，最终以 JSON 和静态资源驱动页面展示。适合用于角色主题站、内容聚合页、粉丝向展示页面等场景。

## Features

- Pinboard-style 首页画布，支持围绕角色内容进行卡片化展示与探索。
- 聚合人物档案、代表作品、社交入口、最新动态等多类内容模块。
- 提供二级页面能力，包括时间线、图片墙与曲库详情页。
- 通过本地 JSON 数据和静态资源驱动页面，便于维护与迭代。
- 配套数据抓取脚本，可整理 X/Twitter、Bilibili、曲库与插图等外部内容。
- 适合部署为纯静态站点，发布成本低，迁移简单。

## Tech Stack

- Frontend: `Vue 3`, `Vue Router`, `Vite`
- UI/UX: 自定义卡片式信息架构、时间线展示、沉浸式视觉布局
- Data: `JSON` 静态数据驱动
- Utilities: `mitt`, `nprogress`
- Tooling: `Node.js`, Python 脚本，用于内容抓取与数据整理

## Getting Started

### 1. Install dependencies

```bash
cd codes
npm install
```

### 2. Start the development server

```bash
npm run dev
```

### 3. Build for production

```bash
npm run build
```

### 4. Preview the production build

```bash
npm run preview
```

开发完成后，前端应用默认运行在 Vite 本地开发环境中；如果需要部署，可直接发布构建产物为静态站点。

## Project Structure

```text
asu-pinwall/
├─ codes/                  # Vue 3 + Vite 前端项目
│  ├─ src/
│  │  ├─ components/       # 业务组件与内容组件
│  │  ├─ data/             # 页面所需静态 JSON 数据
│  │  ├─ router/           # 路由配置
│  │  ├─ utils/            # 工具函数与数据匹配逻辑
│  │  └─ views/            # 首页、时间线、图片墙、详情页
│  └─ public/              # 静态资源与 TimelineJS
├─ docs/                   # PRD、交互方案、设计说明
├─ tools/                  # 数据抓取与预处理脚本
├─ scripts/                # 辅助生成脚本
├─ data/                   # 原始或中间数据文件
└─ x_images/               # 图像相关素材
```

## Pages

- `/`：图钉墙首页，集中展示人物与内容入口。
- `/timeline`：时间线页面，用于回顾重要事件与节点。
- `/image-wall`：官方绘图图片墙。
- `/table-row/:rowIndex`：曲库或表格条目的详情页。

## Data Workflow

- 前端页面主要消费 `codes/src/data/` 下的静态数据。
- `tools/` 与 `scripts/` 中的脚本用于抓取、清洗或生成外部内容数据。
- 抓取结果通常会以 JSON 形式落盘，再由前端映射到对应页面模块。

## Documentation

- 设计与风格说明：`docs/README.zh-CN.md`
- 产品需求文档：`docs/PRD-ASU-Pinwall.md`
- 需求补充与交互方案：`docs/需求说明文档-ASU-Pinwall.md`、`docs/产品交互设计方案-ASU-Pinwall.md`

## Notes

- 当前仓库同时包含前端代码、静态资源和数据抓取脚本，适合小型专题站一体化维护。
- 若需二次开发其他角色主题站点，可复用当前的内容卡片结构、数据组织方式与页面路由设计。
