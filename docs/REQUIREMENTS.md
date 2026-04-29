# PIN WALL · 图钉墙 — 需求说明文档

> 版本：v1.0 · 日期：2026-04-22

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [组件结构](#4-组件结构)
5. [数据模型](#5-数据模型)
6. [交互机制](#6-交互机制)
7. [导航系统](#7-导航系统)
8. [设计系统](#8-设计系统)
9. [资源加载策略](#9-资源加载策略)

---

## 1. 项目概述

**PIN WALL（图钉墙）** 是一个基于浏览器的可交互创意展示空间。其核心概念借鉴了物理世界中将卡片、照片、便条钉在软木展示板上的形式，以数字化方式呈现：用户在一张超大画布上自由浏览被「图钉」固定的信息卡片。

### 1.1 核心定位

- **表现形式**：全屏无滚动条的「无限画布」体验
- **内容载体**：多类型内容卡片（文字、图片、视频、表格、混合）
- **交互方式**：鼠标拖拽 / 滚轮平移 + 小地图快速导航
- **视觉风格**：受 Mistral AI 品牌启发的暖琥珀色设计系统

### 1.2 单页面应用

系统为单页面应用（SPA），无路由跳转。整个交互体验在一个视口内完成，通过画布偏移实现「页面内导航」。

---

## 2. 技术栈

| 分类 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Vue 3 (Composition API) | ^3.5.32 |
| 构建工具 | Vite | ^8.0.9 |
| Vue 插件 | @vitejs/plugin-vue | ^6.0.6 |
| 语言 | JavaScript (ES Module) | — |
| 样式 | 原生 CSS + Vue Scoped CSS | — |
| 状态管理 | 组件内 `ref` / `computed`（无全局 Store） | — |
| 路由 | 无（单页面，画布平移代替路由） | — |
| 数据来源 | 本地 JSON 文件（`cards.json`） | — |

---

## 3. 系统架构

### 3.1 文件目录结构

```
asu-pinwall/
├── codes/                    # 主前端工程
│   ├── index.html            # 入口 HTML，标题：PIN WALL · 图钉墙
│   ├── vite.config.js        # Vite 构建配置
│   ├── package.json          # 依赖声明
│   └── src/
│       ├── main.js           # 应用入口，挂载 #app
│       ├── App.vue           # 根组件，加载数据并传入 PinWall
│       ├── assets/
│       │   └── style.css     # 全局样式（设计变量 + Reset）
│       ├── data/
│       │   └── cards.json    # 卡片数据源
│       └── components/
│           ├── PinWall.vue          # 画布容器（核心控制层）
│           ├── PinCard.vue          # 单张卡片（图钉 + 内容）
│           ├── PinWallPreview.vue   # 小地图 + 导航面板
│           ├── SvgMouseFollower.vue # SVG 鼠标轨迹特效
│           └── content/
│               ├── TextContent.vue    # 文本内容
│               ├── ImageContent.vue   # 图片/图集内容
│               ├── VideoContent.vue   # 视频内容
│               ├── TableContent.vue   # 表格内容
│               └── MixedContent.vue   # 混合块内容
└── docs/
    ├── README.zh-CN.md       # Mistral 风设计系统文档
    └── REQUIREMENTS.md       # 本需求说明文档
```

### 3.2 组件通信关系

```
App.vue
└── PinWall.vue  (props: cards)
    ├── SvgMouseFollower.vue        (独立，无 props)
    ├── PinWallPreview.vue          (props: cards, cardDimensions, offsetX/Y, viewport/canvas 尺寸)
    │   └── emit('navigate', x, y) ──→ PinWall.onNavigate()
    └── PinCard.vue × N             (props: card)
        └── [content/]*.vue         (props: content)
```

### 3.3 状态分布

| 状态 | 所在组件 | 类型 |
|------|----------|------|
| 卡片数据列表 | `App.vue` | `ref(cardsData)` |
| 画布偏移 (offsetX/Y) | `PinWall.vue` | `ref` |
| 拖拽状态 (isDragging) | `PinWall.vue` | `ref` |
| 视口尺寸 | `PinWall.vue` | `ref`，监听 `resize` |
| 卡片 DOM 尺寸字典 | `PinWall.vue` | `ref({})`，初始化后测量 |
| 卡片就绪标记 (cardsReady) | `PinWall.vue` | `ref(false)` |
| 导航动画标记 (isNavigating) | `PinWall.vue` | `ref` |
| 预览面板折叠 (collapsed) | `PinWallPreview.vue` | `ref(false)` |

---

## 4. 组件结构

### 4.1 PinWall.vue — 画布容器

**职责**：全屏视口管理、画布平移控制、子组件编排

**关键参数**：

| 常量 | 值 | 说明 |
|------|----|------|
| `CANVAS_W` | 3840px | 画布总宽度（约视口宽度 ×2） |
| `CANVAS_H` | 2400px | 画布总高度（约视口高度 ×2） |
| `headerH` | 64px | 顶部标题栏高度 |

**层级结构**：

```
.pin-viewport                   固定满屏，overflow:hidden
├── <SvgMouseFollower />         SVG 鼠标彩带（z-index 最低）
├── .pin-wall__header            固定标题栏，z-index: 100，不随画布移动
├── .pin-wall__loading           加载遮罩，仅在 !cardsReady 时显示
├── <PinWallPreview />           左上角悬浮导航，v-if="cardsReady"
└── .pin-wall__canvas            可平移画布（CSS transform）
    ├── .pin-wall__canvas-bg     坐标纸网格纹理（装饰）
    └── <PinCard /> × N          各卡片，绝对定位于画布坐标系
```

**边界限制（clampOffset）**：

```
X 轴：[-(CANVAS_W - viewportWidth), 0]
Y 轴：[-(CANVAS_H - viewportHeight + headerH), -headerH]
```

---

### 4.2 PinCard.vue — 图钉卡片

**职责**：渲染单张卡片，包含图钉头、连接杆、卡片主体，并按 `card.type` 分发内容子组件

**卡片结构**：

```
.pin-card-wrapper               (transform-origin: top center)
├── .pin                        图钉头（圆形，可自定义颜色）
│   └── .pin__shine             高光反射
├── .pin__stem                  图钉连接细杆（2×10px）
└── .pin-card                   白色卡片主体
    ├── .pin-card__accent-bar   顶部 Mistral 渐变色条（4px）
    ├── .pin-card__header       标题区（类型徽章 + 标题文字）
    ├── .pin-card__body         内容区（路由到对应 Content 组件）
    └── .pin-card__footer       底部元数据（meta 字段）
```

**内容类型路由**：

| `card.type` | 组件 | 说明 |
|-------------|------|------|
| `text` | `TextContent.vue` | 纯文本段落 |
| `image` | `ImageContent.vue` | 单图 / 图集 |
| `video` | `VideoContent.vue` | 原生 video 或 iframe |
| `table` | `TableContent.vue` | 表格，支持单元格高亮 |
| `mixed` | `MixedContent.vue` | 多类型 blocks 组合 |

---

### 4.3 PinWallPreview.vue — 小地图导航面板

**职责**：提供画布缩略小地图、四象限快速跳转、前进后退导航、面包屑当前位置显示

**面板结构**：

```
.preview-panel                  左上角悬浮（top:76px, left:12px），可折叠
├── .preview-top                顶部工具栏（高度 40px）
│   ├── 折叠/展开按钮
│   ├── .preview-breadcrumb     面包屑（PIN WALL / 当前象限名）
│   └── .preview-nav            前进 / 后退按钮
└── .preview-body               主体（v-show，折叠时隐藏）
    ├── .minimap                小地图（340px 宽，等比缩放）
    │   ├── 四象限分割线（十字）
    │   ├── 象限标签（INFORMATION / MUSIC / CAREER / NEWS）
    │   ├── 卡片方块（各类型用不同暖色区分）
    │   └── .minimap__viewport  当前视口指示框（橙色边框）
    └── .preview-sections       四个象限指示点（点击跳转）
```

**Minimap 缩放比**：

```
scale = MINIMAP_W(340) / CANVAS_W(3840) ≈ 0.08854
MINIMAP_H = CANVAS_H(2400) × scale ≈ 212px
```

**四象限定义**：

| 象限 | 标签 | 画布位置 |
|------|------|---------|
| 左上 | INFORMATION | (0, 0) 起点 |
| 右上 | MUSIC | 画布 X 轴右半段 |
| 左下 | CAREER | 画布 Y 轴下半段 |
| 右下 | NEWS | 画布右下角 |

---

### 4.4 SvgMouseFollower.vue — 鼠标轨迹特效

**职责**：跟随鼠标绘制 SVG 彩带 / 粒子轨迹，纯视觉装饰，不参与业务逻辑

---

### 4.5 内容子组件（content/）

各内容组件均接受 `content` prop，呈现具体内容：

| 组件 | 关键特性 |
|------|---------|
| `TextContent.vue` | 段落文本展示 |
| `ImageContent.vue` | 单图 / 多图图集，支持 alt 描述 |
| `VideoContent.vue` | 原生 `<video>` 或 `<iframe>` 嵌入 |
| `TableContent.vue` | 行列表格，单元格支持 `{ value, highlight }` 结构 |
| `MixedContent.vue` | `blocks[]` 数组，每个 block 含 type + content 递归渲染 |

---

## 5. 数据模型

### 5.1 卡片（Card）字段说明

```json
{
  "id":      "唯一标识符（字符串）",
  "type":    "text | image | video | table | mixed",
  "x":       "画布 X 坐标（px，画布左上为原点）",
  "y":       "画布 Y 坐标（px）",
  "rotate":  "旋转角度（deg，可选，默认 0）",
  "zIndex":  "层叠顺序（可选，默认 1）",
  "title":   "卡片标题（可选）",
  "meta":    "底部元数据文字（可选）",
  "pin": {
    "color": "图钉颜色（CSS 色值，可选，默认品牌橙）"
  },
  "layout": {
    "w": "声明宽度（px，可选，用于 minimap 渲染）",
    "h": "声明高度（px，可选）"
  },
  "content": "内容数据（结构因 type 而异，见下）"
}
```

### 5.2 各类型 content 结构

**text**
```json
{ "text": "纯文本字符串" }
```

**image**
```json
{
  "src": "图片路径",
  "alt": "描述文字（可选）",
  "images": [{ "src": "...", "alt": "..." }]
}
```

**video**
```json
{
  "src": "视频文件路径或 iframe URL",
  "type": "mp4 | iframe"
}
```

**table**
```json
{
  "headers": ["列名1", "列名2"],
  "rows": [
    ["值", { "value": "值", "highlight": true }]
  ]
}
```

**mixed**
```json
{
  "blocks": [
    { "type": "text | image | video | table", "content": { ... } }
  ]
}
```

### 5.3 卡片尺寸优先级

小地图中渲染卡片方块时，尺寸来源按以下优先级决定：

1. **父组件实测 DOM 尺寸**（`cardDimensions[card.id]`）— 最精准
2. **数据中声明的 `layout.w/h`**
3. **按类型的默认值**（text: 300×248 / image: 400×312 / video: 380×268 / table: 360×228 / mixed: 400×292）
4. **通用回退值**（320×240）

---

## 6. 交互机制

### 6.1 画布平移

| 交互方式 | 行为 |
|---------|------|
| 鼠标左键按住拖拽（画布空白区域） | 平滑移动画布 |
| 鼠标滚轮（`wheel` 事件） | 双轴平移（不缩放） |
| 点击卡片内部区域 | 不触发画布拖拽（保留卡片内部交互） |
| 从 Minimap 导航 | 触发带 CSS 过渡动画（0.5s ease）的平移 |

### 6.2 画布边界约束

画布偏移通过 `clampOffset` 函数限制，确保：
- 画布不会超出左边 / 上边（视口始终能看到内容）
- 画布不会超出右边 / 下边（无内容区域不可见）
- Y 轴上边留出 `headerH = 64px` 的标题栏空间

### 6.3 导航动画

当用户通过小地图或区域点击触发导航时：
- `isNavigating` 设为 `true`，画布 CSS class 切换为 `pin-wall__canvas--navigating`
- 此时启用 `transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)` 平滑过渡
- 550ms 后自动关闭导航动画状态，恢复即时拖拽响应

### 6.4 卡片旋转

每张卡片通过 `rotate` 字段设定固定旋转角度（单位 deg），`transform-origin` 为卡片包装元素的顶部中心（图钉所在位置），视觉上形成「被图钉钉住」的倾斜感。

---

## 7. 导航系统

### 7.1 小地图（Minimap）

小地图以 340px 宽度，按统一缩放比（≈1:11.3）呈现整个 3840×2400 画布的缩略视图：

- **橙色边框矩形**：实时反映当前视口在画布上的位置和大小
- **彩色方块**：代表各张卡片，颜色按内容类型区分（暖色系）
- **点击跳转**：点击 minimap 任意位置，画布以该点为中心定位

### 7.2 四象限导航

画布被虚拟划分为四个象限，各自对应不同主题内容区域：

- **INFORMATION**（左上）：起始视角，坐标 (0, 0)
- **MUSIC**（右上）：画布右半侧
- **CAREER**（左下）：画布下半侧
- **NEWS**（右下）：画布右下角

当前所在象限通过视口中心点在画布上的位置自动判断，在面包屑中实时显示。

### 7.3 区域导航点 & 前进 / 后退

- **区域指示点**：小地图下方四个方块点，代表四象限；当前象限的点以品牌橙高亮放大
- **前进 / 后退按钮**：Finder 风格，按象限顺序（INFORMATION → MUSIC → CAREER → NEWS → INFORMATION）循环切换

---

## 8. 设计系统

项目采用受 **Mistral AI** 官网视觉语言启发的设计系统，核心特征为「温暖的欧式极简主义」。

### 8.1 色彩体系

| 角色 | 色值 | 用途 |
|------|------|------|
| 品牌橙 (Mistral Orange) | `#fa520f` | 主强调色、图钉、视口边框 |
| 暖象牙 (Warm Ivory) | `#fffaeb` | 页面背景色 |
| 奶油色 (Cream) | `#fff0c2` | 次要背景、按钮 |
| Mistral Black | `#1f1f1f` | 主文字、深色元素 |
| 阳光琥珀 (Sunshine 700) | `#ffa110` | 次级强调、装饰 |
| 亮金 (Bright Yellow) | `#ffd900` | 渐变起点 |
| 阴影底色 | `rgba(127, 99, 21, ...)` | 所有阴影均为暖琥珀调 |

**标志性渐变（Mistral Block Gradient）**：
```css
#ffd900 → #ffe295 → #ffa110 → #ff8105 → #fb6424 → #fa520f
```
用于卡片顶部色条、品牌方块标识。

### 8.2 排版规则

- **字体族**：`Arial`（系统回退），搭配 `ui-sans-serif, system-ui`
- **全系统字重 400**（不使用加粗），通过字号与颜色建立层级
- **字号体系**：Feature（24px）/ Caption（14px）/ 正文（16px）等
- **字母间距**：展示级文字使用激进负字距；标签类使用正字距营造大写欧式感

### 8.3 阴影体系

所有抬升元素均使用多层暖琥珀阴影：

```css
box-shadow:
  rgba(127, 99, 21, 0.12) -8px 16px 39px,
  rgba(127, 99, 21, 0.10) -33px 64px 72px,
  rgba(127, 99, 21, 0.06) -73px 144px 97px;
```

营造「黄金时刻光照」的浮起感，区别于常见的冷灰阴影体系。

### 8.4 圆角

- **接近零圆角**（锐利几何）为主导原则
- 卡片、按钮、面板等元素均为方角，与暖色形成「软色 × 硬几何」的视觉张力

### 8.5 间距体系

基准 8px，常用刻度：`2 / 4 / 6 / 8 / 10 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64px`

### 8.6 CSS 变量（style.css 定义）

```css
--color-brand-orange
--color-warm-ivory
--color-white
--color-mistral-black
--color-text-primary
--color-text-secondary
--gradient-mistral-block
--shadow-card
--shadow-pin
--font-family
--fs-subheading / --fs-feature / --fs-caption
--space-2 / --space-5 / --space-6 / --space-8 / --space-12
--radius
```

---

## 9. 资源加载策略

### 9.1 加载时序

```
1. main.js 挂载 App.vue
2. App.vue 读取 cards.json → 传入 PinWall
3. PinWall 渲染所有 PinCard 到 DOM（此时 cardsReady = false）
4. nextTick 后，收集所有卡片内 <img> 元素
5. Promise.all 等待所有图片 load / error
6. 图片就绪后，测量每张卡片的 offsetWidth / offsetHeight
7. 将尺寸字典存入 cardDimensions，设置 cardsReady = true
8. PinWallPreview 组件挂载（v-if="cardsReady"），minimap 尺寸精准
```

### 9.2 加载状态 UI

- 卡片资源加载期间显示全屏加载层（毛玻璃背景 + spinner 动画）
- `aria-busy` / `aria-live` / `aria-label` 属性保障无障碍访问
- 加载完成后遮罩隐藏，预览面板同步出现

### 9.3 视口响应式

`PinWall` 通过监听 `window.resize` 事件实时更新 `viewportWidth / viewportHeight`，并同步传递给 `PinWallPreview`，确保 minimap 视口指示框始终准确。

---

*本文档基于 2026-04-22 项目源码状态生成，如后续有架构变更请同步更新。*
