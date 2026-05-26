/**
 * 将 asu-discography、albemuth-discography 目录下静态资源打包为 filename → 最终 URL
 * 需与 data/asu_music_data.json、data/albemuth_music_data.json 内 `discography` 条目的 `src` 一致
 */
const asuModules = import.meta.glob('../assets/images/asu-discography/*', {
  eager: true,
  query: '?url',
  import: 'default'
})
const albemuthModules = import.meta.glob('../assets/images/albemuth-discography/*', {
  eager: true,
  query: '?url',
  import: 'default'
})
const asuCoverModules = import.meta.glob('../assets/images/asu-cover/*', {
  eager: true,
  query: '?url',
  import: 'default'
})

const coverUrlByFileName = new Map()
for (const modules of [asuModules, albemuthModules, asuCoverModules]) {
  for (const path of Object.keys(modules)) {
    const name = path.split(/[/\\]/).pop()
    if (name) {
      coverUrlByFileName.set(name, modules[path])
    }
  }
}

/**
 * @param {string | undefined} fileName
 * @returns {string | null}
 */
export function getDiscographyCoverUrl(fileName) {
  if (typeof fileName !== 'string' || !fileName.trim()) return null
  const key = fileName.trim()
  return coverUrlByFileName.get(key) ?? null
}
