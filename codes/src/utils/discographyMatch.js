/**
 * 将 asu 表格中的日文日期（如 2021年11月18日）规范为可比较的 YYYY.MM.DD
 */
export function parseAsuDateToKey(dateStr) {
  if (typeof dateStr !== 'string' || !dateStr.trim()) return null
  const m = dateStr.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/)
  if (!m) return null
  const y = m[1]
  const month = String(Number(m[2])).padStart(2, '0')
  const day = String(Number(m[3])).padStart(2, '0')
  return `${y}.${month}.${day}`
}

/**
 * 将 discography 的 Date（如 2021.11.18 或 2024.8.28）规范为 YYYY.MM.DD
 */
export function parseDiscDateToKey(dateStr) {
  if (typeof dateStr !== 'string' || !dateStr.trim()) return null
  const parts = dateStr.split('.').map((p) => p.trim())
  if (parts.length !== 3) return null
  const [y, mo, d] = parts
  if (!/^\d{4}$/.test(y)) return null
  return `${y}.${String(Number(mo)).padStart(2, '0')}.${String(Number(d)).padStart(2, '0')}`
}

/**
 * 从「スロウリー / Slowly」或「Spiral」类字符串抽取用于匹配的曲名核心片段
 */
export function extractAsuCoreTitle(tableTitle) {
  if (typeof tableTitle !== 'string') return ''
  let s = tableTitle.replace(/\s+/g, ' ').trim()
  // 取首对 「」 内内容，无则整段
  const quote = s.match(/「([^」]+)」/)
  if (quote) s = quote[1]
  // 日/ 或 / 前一般为日文或主标题
  const slash = s.split(/[/／]/)[0]
  return slash.replace(/\s+/g, ' ').trim()
}

/**
 * 曲名与 discography.Title 是否匹配（等值或明显包含，避免过短误匹配）
 */
function titlesCompatible(core, discTitle) {
  if (!core || !discTitle) return false
  const a = core.trim()
  const b = discTitle.trim()
  if (a === b) return true
  const short = a.length <= b.length ? a : b
  const long = a.length > b.length ? a : b
  if (short.length < 2) return false
  return long.includes(short)
}

/**
 * 在 discography 条目中为 asu 行查找最佳匹配（先同日再标题；无则全库标题匹配）
 * @param {{ date: string, title: string }} asuRow
 * @param {Array<{ Date: string, Title: string, Desc: string, src: string }>} entries
 * @returns {object | null}
 */
export function findDiscographyEntry(asuRow, entries) {
  if (!asuRow || !Array.isArray(entries) || !entries.length) return null
  const dateKey = parseAsuDateToKey(asuRow.date)
  const core = extractAsuCoreTitle(asuRow.title)
  if (!core) return null

  const sameDay = dateKey
    ? entries.filter((e) => parseDiscDateToKey(e.Date) === dateKey)
    : []

  const pickBest = (cands) => {
    if (!cands.length) return null
    const byTitle = cands.find((e) => titlesCompatible(core, e.Title))
    return byTitle ?? null
  }

  const fromDate = pickBest(sameDay)
  if (fromDate) return fromDate

  return pickBest(entries) ?? null
}

const BV_RE = /(BV[0-9A-Za-z]+)/i

/**
 * 从 bilibili 视频页 URL 解析 bvid
 */
export function extractBvidFromUrl(url) {
  if (typeof url !== 'string' || !url) return null
  try {
    const u = url.startsWith('//') ? `https:${url}` : url
    if (!/bilibili\.com/i.test(u)) return null
    const m = u.match(BV_RE)
    return m ? m[1] : null
  } catch {
    return null
  }
}

/**
 * 构建 bilibili 嵌入式 player URL
 */
export function getBilibiliPlayerUrl(bvid) {
  if (!bvid) return null
  const id = bvid.startsWith('BV') ? bvid : `BV${bvid}`
  return `https://player.bilibili.com/player.html?bvid=${encodeURIComponent(
    id
  )}&page=1&high_quality=1&autoplay=0`
}
