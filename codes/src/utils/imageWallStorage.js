/** 图钉墙 → 图片墙页面 传递图片列表用的 sessionStorage 键 */
export const IMAGE_WALL_STORAGE_KEY = 'pinwall-image-wall-payload'

/**
 * @param {{ src: string, alt?: string }[]} images
 */
export function setImageWallPayload(images) {
  sessionStorage.setItem(
    IMAGE_WALL_STORAGE_KEY,
    JSON.stringify({ images: Array.isArray(images) ? images : [] })
  )
}

/**
 * @returns {{ src: string, alt?: string }[]}
 */
export function getImageWallPayload() {
  try {
    const raw = sessionStorage.getItem(IMAGE_WALL_STORAGE_KEY)
    if (!raw) return []
    const data = JSON.parse(raw)
    return Array.isArray(data?.images) ? data.images : []
  } catch {
    return []
  }
}
