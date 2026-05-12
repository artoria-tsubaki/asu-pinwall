import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const dir = path.join(__dirname, '../codes/src/assets/images/illus')
const kw = [
  '夏服', '冬装', '生日贺图', '舞台', '自拍切片', 'Q版', '线稿', '配色稿', '联动', '神椿',
  '深脊界', '演唱会', 'MV花絮', '收录纪念', '一周年', '冬季', '樱花', '夜景', '室内', '海边',
  '制服', '春服', '侧身', '回眸', '全身立绘', '私服', '公式', '直播', '纪念', 'FanArt风官图',
  '三周年', '线摄', '涂鸦'
]
const files = fs
  .readdirSync(dir)
  .filter((f) => !f.endsWith('.json') && /\.(jpg|jpeg|png|webp)$/i.test(f))
  .sort()
const items = files.map((file, i) => ({
  file,
  title: kw[i % kw.length]
}))
const out = { version: 1, items }
fs.writeFileSync(path.join(dir, 'illus.json'), JSON.stringify(out, null, 2), 'utf8')
console.log('wrote', items.length, 'entries to illus.json')
