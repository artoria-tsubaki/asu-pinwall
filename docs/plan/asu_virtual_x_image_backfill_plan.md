# 文件化执行计划：全量回填并支持增量同步的 X 图片抓取

## Summary
将现有 [tools/fetch_x_images_unofficial.py](C:/Users/Artor/Desktop/ai-demo/asu-pinwall/tools/fetch_x_images_unofficial.py) 从“已验证可抓取最近一批图片推文”完善为“可完整回填 `@ASU_virtual` 历史所有图片推文，并支持后续重复运行增量同步”的稳定方案。

当前已验证事实：
- Cookie 导入可用
- `Media` 时间线可读取
- `photo` 图片可识别
- 原图地址可提取
- 图片和 JSON 可成功落盘

最近一次运行结果：
- 扫描 50 条媒体推文
- 命中 43 条图片推文
- 成功下载 43 张图片
- 成功写入 `data/asu_virtual_x_images.json`

## Implementation Changes
- 全量分页抓取
  - 保持默认抓 `Media` 时间线。
  - 持续调用 `Result.next()` 直到无下一页，或达到显式扫描上限。
  - 新增 `--fetch-all` 参数，开启后优先执行完整历史回填。
  - `--max-tweets` 保留为安全上限，便于调试和限量抓取。
- 全量回填 + 增量同步
  - 首次运行：尽量抓完整个历史媒体时间线。
  - 后续运行：继续按 `tweet_id_序号` 去重，自动跳过已下载图片。
  - 增量模式下加入“连续多页无新增则提前停止”的策略，避免每次都翻完整历史。
- 停止条件
  - 没有下一页时停止。
  - 命中 `--since` 指定的时间下界时停止。
  - 增量模式下连续若干页都没有新增图片时停止。
- 数据一致性
  - 下载成功后再写入 manifest。
  - 若本地文件存在但 JSON 缺记录，重跑时补记录。
  - 若 JSON 有记录但本地文件缺失，重跑时补文件。
  - 继续使用 `name=orig` 规范化。
- 运行体验
  - 默认输出简洁进度日志：页数、累计推文数、图片数、下载数、跳过数。
  - `--debug-sample` 仅用于排障。
  - README 或脚本头部补充两套标准命令：
    - 首次全量回填
    - 后续增量同步

## Public Interfaces
- 保留现有参数：
  - `--user`
  - `--cookie-header-file`
  - `--cookies-file`
  - `--proxy`
  - `--since`
  - `--until`
  - `--max-tweets`
  - `--tweet-type`
  - `--verbose`
  - `--debug-sample`
- 新增参数：
  - `--fetch-all`
    - 含义：完整抓取历史媒体时间线
  - 可选新增：
    - `--stop-after-empty-pages`
    - 含义：增量模式下连续多少页无新增后停止

## Test Plan
- 全量分页测试
  - 启用 `--fetch-all`，确认会继续翻页直到无下一页。
- 增量重跑测试
  - 连续执行两次，第二次应主要表现为跳过已存在图片。
- 时间范围测试
  - 设置较新的 `--since`，确认会按时间下界停止。
- 数据修复测试
  - 删除单张已记录图片后重跑，确认会补回。
  - 删除单条 JSON 记录后重跑，确认会补回。
- 媒体过滤测试
  - `photo` 下载，`video` 和 `animated_gif` 不进入结果。
- 输出格式测试
  - JSON 始终只保留：
    - `filename`
    - `tweet_time`

## Default Commands
- 首次全量回填：
```powershell
& "C:\Users\Artor\AppData\Local\Programs\Python\Python314\python.exe" `
  tools\fetch_x_images_unofficial.py `
  --user ASU_virtual `
  --cookie-header-file local_x_cookie.txt `
  --cookies-file token\x_cookies_ASU_virtual.json `
  --fetch-all `
  --proxy <YOUR_PROXY>
```

- 后续增量同步：
```powershell
& "C:\Users\Artor\AppData\Local\Programs\Python\Python314\python.exe" `
  tools\fetch_x_images_unofficial.py `
  --user ASU_virtual `
  --cookies-file token\x_cookies_ASU_virtual.json `
  --proxy <YOUR_PROXY>
```

## Assumptions
- 目标账号仍为 `ASU_virtual`。
- 登录态继续以浏览器导出的 Cookie 为主，不再依赖 `twikit.login(...)`。
- “带图片推文”定义为 `photo` 类型媒体，不含视频封面。
- 落盘路径保持不变：
  - 图片：`C:\Users\Artor\Desktop\ai-demo\asu-pinwall\x_images\ASU_virtual`
  - JSON：`C:\Users\Artor\Desktop\ai-demo\asu-pinwall\data\asu_virtual_x_images.json`
- 如果 X 再次变更内部接口，Playwright 作为独立兜底方案，不与当前主路径混用。
