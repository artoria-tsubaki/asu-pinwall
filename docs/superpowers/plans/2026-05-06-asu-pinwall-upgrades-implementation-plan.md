# ASU Pinwall 功能升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成三块能力——（1）官方绘图入口卡片与详情页瀑布流视觉升级；（2）「最新消息」推文数据由每日定时 Python 脚本 + GitHub Actions 自动更新并入库；（3）career 区域出道天数卡片（及可选扩展）重新设计，缓解区域空旷感。

**Architecture:** 官方绘图沿用 `HomeView` 注入图列表 → `ImageWallRotatingContent` 轮播 → `sessionStorage` 传递 → `ImageWallView` 瀑布流；在不大改数据流的前提下优化组件样式与布局。News 侧将稳定 JSON 路径作为唯一信源，CI 定时覆盖或追加写入并由前端静态导入。Career 侧重构 `DaysContent` 展示层，必要时在 `cards.json` 增卡或调坐标。

**Tech Stack:** Vue 3、Vite、Vue Router、`sessionStorage`；Python 3、`tweepy`、Twitter/X API v2 Bearer Token；GitHub Actions（`cron` + `actions/checkout` + `actions/setup-python` + 可选 `pnpm/npm` 校验）。

---

## 文档使用说明

- 每个 **Epic** 开头有 **材料门**：开工前须向需求方确认所列材料/决策已就绪。
- 建议 **实施顺序**：Epic B → Epic A → Epic C（数据管线先稳，再做视觉与 career 布局）。
- 单 Epic 可独立查阅；合并本文件便于总览与排期。

---

## Epic A：官方绘图卡片与详情页瀑布流

### 材料门（Epic A 开工前必答）

在开始 **Task A.1** 前请确认已提供或决策：

- [ ] 官方绘图图片是否已放入 `codes/src/assets/images/illus/`（或约定的新目录），格式为 `jpg/jpeg/png/webp`。
- [ ] 是否有视觉参考（截图/Figma/文字描述）：圆角、边框、轮播指示、封面叠层文案等。
- [ ] 是否需要每图独立标题/来源；若需要，元数据从文件名、sidecar JSON 还是手工维护表来。
- [ ] 详情页除瀑布流外，是否需要点开大图、键盘导航等（影响工作量，默认仅美化布局与 hover）。

---

### Task A.1：盘点数据流与约束

**Files:**

- Read: `codes/src/views/HomeView.vue`（`import.meta.glob` 收集插图）
- Read: `codes/src/components/content/ImageWallRotatingContent.vue`（入口轮播、`setImageWallPayload`）
- Read: `codes/src/utils/imageWallStorage.js`（`IMAGE_WALL_STORAGE_KEY`）
- Read: `codes/src/views/ImageWallView.vue`（CSS `column-count` 瀑布流、懒加载、尺寸预取）

- [ ] **Step 1：** 对照上述文件，记录「轮播 → 存储 → 详情页」字段：`{ src, alt? }` 是否足够承载后续标题/索引展示。

- [ ] **Step 2：** 若 `illus` 目录为空，在计划执行时增加 `ImageWallRotatingContent` 与 `ImageWallView` 的空状态文案与占位视觉（与 Epic A 设计稿一致），避免用户点击无反馈。

---

### Task A.2：重设计图钉墙「官方绘图」入口卡片（`image-wall-teaser`）

**Files:**

- Modify: `codes/src/components/content/ImageWallRotatingContent.vue`
- May modify: `codes/src/components/PinCard.vue`（若需在 `pin-card--image-teaser` 层级加类名或结构调整）
- May modify: `codes/src/data/cards.json`（`image-wall-teaser` 的 `layout`、`meta`、`content.intervalMs`）

- [ ] **Step 1：** 按设计稿调整 `ImageWallRotatingContent` 模板：例如底部渐变叠层、角标「官方绘图」、当前张数/总张数、轮播指示点或细线进度（不改变 `openWall` 与 `setImageWallPayload(slides.value.map(...))` 的语义）。

- [ ] **Step 2：** 调整 scoped 样式：hover/focus-visible、过渡时长、`aspect-ratio` 是否与 `cards.json` 中 `layout.h` 视觉一致。

- [ ] **Step 3：** 确认 `aria-label` 仍准确描述「进入瀑布流」行为；若增加装饰性元素，勿破坏键盘 Enter/Space 触发。

---

### Task A.3：美化 `ImageWallView` 瀑布流与单图卡片

**Files:**

- Modify: `codes/src/views/ImageWallView.vue`

- [ ] **Step 1：** 优化 `.image-wall-page__masonry` 与 `.image-wall-page__cover-card`：列间距、最大宽度、背景页与卡片对比度（沿用 `codes/src/assets/style.css` 中 CSS 变量）。

- [ ] **Step 2：** 将 `imageTitlePlaceholder` 替换为真实逻辑或与设计一致的占位规则（例如 `图片 {{ index + 1 }}` 或来自 payload 扩展字段）；若扩展 payload，需同步修改 `setImageWallPayload` 调用处类型与序列化。

- [ ] **Step 3：** 保留「全部尺寸预取后再 `dimensionsReady`」逻辑，避免 `column-count` 重排闪烁；若增加 hover 缩放，使用 `transform` 并注意 `break-inside`。

- [ ] **Step 4：** 本地验证：无图、单图、多图横竖混排；从首页入口进入与直接刷新详情页（`sessionStorage` 空）行为。

---

### Task A.4：Epic A 验收

- [ ] 首页官方绘图卡片视觉、交互、无障碍与现有图钉墙拖拽不冲突。
- [ ] 详情页滚动性能可接受；懒加载与预取逻辑无回归。

---

## Epic B：News（最新消息）每日自动更新

### 材料门（Epic B 开工前必答）

在开始 **Task B.1** 前请确认已提供或决策：

- [ ] GitHub 仓库 Settings → Secrets：`TWITTER_TOKEN`（Bearer Token）已配置；Token 是否有 `read` 用户推文权限。
- [ ] 固定拉取的 X 用户名（当前前端为 `ASU_virtual`，见 `codes/src/data/cards.json`）。
- [ ] 定时策略：UTC 或北京时间每天在几时运行；是否允许与手动 `workflow_dispatch` 并存。
- [ ] 产物策略：仅保留「最新 5 条」写入 JSON，还是写入全量再由 `TweetsCarouselContent` `slice(0, 5)`（推荐后者便于排错）。

---

### Task B.1：稳定 JSON 契约与前端导入路径

**Files:**

- Modify: `codes/src/views/HomeView.vue`（`import ... from '../../../data/tweets_....json'`）
- Create or rename: `data/tweets_ASU_virtual_latest.json`（或团队约定的固定文件名）
- Reference format: `data/tweets_ASU_virtual_20260427_155644.json`（数组，元素含 `media`、`start_date`、`text`）

- [ ] **Step 1：** 在仓库根目录 `data/` 下确定**唯一**被前端导入的文件名（例如 `tweets_ASU_virtual_latest.json`），格式与现有样本一致。

- [ ] **Step 2：** 修改 `HomeView.vue` 中静态 import 指向该固定路径；构建 `npm run build`（在 `codes/` 下）确保 Vite 能解析。

---

### Task B.2：整理 Python 输出脚本（写入固定路径）

**Files:**

- Modify or add: `tools/fetch_tweets_latest_for_pinwall.py`（建议新建，职责单一）
- Reference: `tools/fetch_tweets.py`（`build_event`、`fetch_via_api` 模式）

建议新脚本行为：

- 使用环境变量 `TWITTER_TOKEN`。
- 参数：`--user ASU_virtual`、`--limit 20`（或 5 若只存 5 条）、`--out data/tweets_ASU_virtual_latest.json`（相对仓库根）。
- 使用与 `fetch_tweets.py` 相同的 event 结构，保证 `TweetsCarouselContent` 无需改字段。

- [ ] **Step 1：** 实现脚本：调用 API → 得到 `events` 列表 → `json.dump(..., ensure_ascii=False, indent=2)` 写入 `--out`。

- [ ] **Step 2：** 失败时**不覆盖**已有 `--out` 文件（检测到非 0 退出码或异常则打印 stderr 并 exit 1）；成功则覆盖。

---

### Task B.3：依赖与本地运行说明

**Files:**

- Create: `tools/requirements-tweets.txt`（内容示例见下）

```text
tweepy>=4.14.0
```

- [ ] **Step 1：** 添加 `requirements-tweets.txt` 后，在 README 或 `docs/` 中简短记录一行安装与运行命令（若项目已有中文文档，写入 `docs/README.zh-CN.md` 中「数据更新」小节，保持与仓库习惯一致）。

---

### Task B.4：GitHub Actions 工作流

**Files:**

- Create: `.github/workflows/update-latest-tweets.yml`

建议工作流要点：

- `on.schedule`：`cron` 每天一次（按材料门约定时区换算为 UTC）。
- `on.workflow_dispatch`：允许手动触发。
- `permissions.contents: write`（若同仓提交 JSON）。
- `steps`：`checkout` → `setup-python` → `pip install -r tools/requirements-tweets.txt` → `python tools/fetch_tweets_latest_for_pinwall.py --user ASU_virtual --limit 20 --out data/tweets_ASU_virtual_latest.json`（env `TWITTER_TOKEN`）。
- 若 `git diff --quiet data/tweets_ASU_virtual_latest.json` 则无提交；否则 `git config user` → `git add` → `git commit -m "chore(data): refresh latest tweets"` → `git push`（分支默认 `main`，若仓库用 `master` 需改）。

- [ ] **Step 1：** 添加 workflow 文件并在测试分支用 `workflow_dispatch` 跑通一次。

- [ ] **Step 2：** 确认不会在日志中打印 Token；`.gitignore` 若需加入 `token/` 或 `*TOKEN*.json` 防误提交（按仓库现状调整）。

---

### Task B.5：Epic B 验收

- [ ] 手动删除/旧数据后跑一次 Action，前端轮播显示新正文与日期。
- [ ] Token 失效时 workflow 失败且不损坏旧 JSON。

---

## Epic C：Career 区域与出道天数卡片

### 材料门（Epic C 开工前必答）

在开始 **Task C.1** 前请确认已提供或决策：

- [ ] **范围**：仅重设计 `debut-days` 单卡，还是允许在 `cards.json` 增加 1～2 张 career 相关卡（如里程碑、快速链到 `/timeline`）。
- [ ] **内容**：除出道日外，是否有固定文案、下一周年纪念日期、或需从 `codes/src/data/timeline.json` 拉一条「最新动态」摘要。
- [ ] **画布**：`debut-days` 当前坐标见 `cards.json`；是否允许增大 `layout` 或移动 `x/y` 以免与邻近卡片重叠。

---

### Task C.1：增强 `DaysContent` 展示（首选，改动集中）

**Files:**

- Modify: `codes/src/components/content/DaysContent.vue`
- May modify: `codes/src/data/debut.json`（新增可选字段，如 `tagline`、`milestones` 数组，需与需求一致）

- [ ] **Step 1：** 在设计稿指导下调整模板：例如顶部 kicker、分层排版、下一里程碑倒计时（若 `debut.json` 增加 `anniversaryMonthDay` 等字段则先扩展 JSON 再读入）。

- [ ] **Step 2：** 调整样式：在保持 **固定舞台高度** 或按设计改为自适应时，验证 `PinWall.vue` 收集卡片尺寸与预览不受影响。

- [ ] **Step 3：** 保留原有日期计算与注释；切换 `DAYS` / `Y·M·D` 与「活动时间线」链接行为保持不变，除非需求明确变更。

---

### Task C.2（可选）：扩展 career 区域多张卡片

**Files:**

- Modify: `codes/src/data/cards.json`
- May add: 新 `type` 或复用 `text`/`mixed` 组件（优先复用现有 `PinCard` 路由，避免新造类型）

- [ ] **Step 1：** 若材料门确认增加卡片，在 `career-video` 与 `debut-days` 附近布置新卡坐标，避免与 `original-songs-table` 等远距卡片无关冲突。

- [ ] **Step 2：** 若新卡需静态资源，在 `HomeView.vue` 中按 `career-video` 模式注入本地 URL。

---

### Task C.3：Epic C 验收

- [ ] 出道天数在不同日期下数字与 Y·M·D 正确。
- [ ] 图钉墙加载与拖拽正常；career 区域视觉密度符合预期。

---

## 全量回归清单（三 Epic 均可完成后执行）

- [ ] `codes/` 下 `npm run build` 通过。
- [ ] 首页所有卡片类型仍渲染：`profile`、`social-grid`、`video`、`days`、`image-wall-teaser`、`tweets`、`table`。
- [ ] 从官方绘图进入 `ImageWall` 再返回，`sessionStorage` 行为正常。

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-05-06 | 初版：合并官方绘图、News 定时更新、Career 出道天数三项计划 |
