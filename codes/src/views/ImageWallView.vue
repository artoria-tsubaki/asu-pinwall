<template>
  <div class="image-wall-page">
    <button
      type="button"
      class="image-wall-page__close"
      aria-label="关闭并返回"
      @click="goBack"
    >
      <span class="image-wall-page__close-icon" aria-hidden="true">×</span>
    </button>

    <Teleport to="body">
      <div
        v-if="previewIndex !== null"
        class="image-wall-page__preview-backdrop"
        role="dialog"
        aria-modal="true"
        aria-label="图片预览"
        @click="closePreview"
      >
        <div class="image-wall-page__preview-toolbar" @click.stop>
          <button
            type="button"
            class="image-wall-page__preview-btn image-wall-page__preview-btn--download"
            :disabled="previewDownloadBusy"
            :aria-label="previewDownloadBusy ? '下载中' : '下载图片'"
            @click="downloadPreviewImage"
          >
            <svg
              v-if="!previewDownloadBusy"
              class="image-wall-page__preview-btn-icon"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="square"
              stroke-linejoin="miter"
              aria-hidden="true"
            >
              <path d="M12 3v13M7 11l5 5 5-5" />
              <path d="M4 20h16" />
            </svg>
            <svg
              v-else
              class="image-wall-page__preview-btn-icon image-wall-page__preview-btn-icon--spin"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="square"
              aria-hidden="true"
            >
              <path d="M12 2a10 10 0 0 1 10 10" />
            </svg>
          </button>
          <button
            type="button"
            class="image-wall-page__preview-btn image-wall-page__preview-btn--close"
            aria-label="关闭预览"
            @click="closePreview"
          >
            <svg
              class="image-wall-page__preview-btn-icon"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="square"
              stroke-linejoin="miter"
              aria-hidden="true"
            >
              <path d="M4 4l16 16M20 4L4 20" />
            </svg>
          </button>
        </div>
        <div class="image-wall-page__preview-stage" @click="closePreview">
          <img
            v-if="previewImage"
            :src="previewImage.src"
            :alt="previewImage ? cardDisplayTitle(previewImage) : imageTitlePlaceholder"
            class="image-wall-page__preview-img"
            decoding="async"
            @click.stop
          />
        </div>
      </div>
    </Teleport>

    <main ref="scrollRootRef" class="image-wall-page__main">
      <div
        v-if="wallItems.length && dimensionsReady"
        class="image-wall-page__search-row"
      >
        <input
          id="image-wall-search"
          v-model="searchQuery"
          type="search"
          class="image-wall-page__search"
          placeholder="按标题搜索…"
          autocomplete="off"
          aria-label="按标题筛选图片"
        />
      </div>
      <div v-if="!wallItems.length" class="image-wall-page__empty">
        暂无图片，请从图钉墙卡片进入。
      </div>
      <div v-else-if="!dimensionsReady" class="image-wall-page__loading">
        <span class="image-wall-page__loading-dot" />
        <span class="image-wall-page__loading-dot" />
        <span class="image-wall-page__loading-dot" />
      </div>
      <div v-else-if="hasActiveSearch && !filteredIndices.length" class="image-wall-page__empty">
        没有匹配的标题。
      </div>
      <div v-else class="image-wall-page__masonry">
        <div
          v-for="i in filteredIndices"
          :key="i + wallItems[i].src"
          class="image-wall-page__item"
          :data-lazy-index="i"
        >
          <div class="image-wall-page__cover-wrap">
            <div class="image-wall-page__cover-card">
              <div
                class="image-wall-page__img-wrapper"
                :style="{ aspectRatio: dimensions[i] ? `${dimensions[i].w} / ${dimensions[i].h}` : '3 / 2' }"
                role="button"
                tabindex="0"
                aria-label="查看大图"
                @click="openPreview(i)"
                @keydown.enter.prevent="openPreview(i)"
                @keydown.space.prevent="openPreview(i)"
              >
                <img
                  v-if="loaded[i]"
                  :src="wallItems[i].src"
                  :alt="cardDisplayTitle(wallItems[i])"
                  class="image-wall-page__cover-img"
                  decoding="async"
                />
              </div>
              <p class="image-wall-page__image-title">{{ cardDisplayTitle(wallItems[i]) }}</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
defineOptions({ name: 'ImageWallView' })

import { onMounted, onUnmounted, reactive, ref, nextTick, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getImageWallPayload } from '../utils/imageWallStorage.js'

/** 无标题数据时的兜底文案 */
const imageTitlePlaceholder = '图片标题'

const router = useRouter()
const wallItems = ref([])
const searchQuery = ref('')
const scrollRootRef = ref(null)
/** 已通过 IntersectionObserver 决定加载的图片下标（进入视口或预取区后才置 true） */
const loaded = reactive({})
/** 预加载后记录的图片原始宽高，用于 aspect-ratio 锁定占位高度，防止懒加载时 CSS 列布局重排 */
const dimensions = reactive({})
/**
 * 所有图片尺寸均已确定后才置 true，瀑布流在此之前不渲染。
 * 原因：CSS column-count 布局会在任意 item 高度变化时重新平衡列分布，
 * 导致已入场的图片被"挤"到其他位置。等全部尺寸就绪后首次渲染可确保布局稳定。
 * 带宽代价为零——图片本就在预加载，仅推迟了首次显示时机。
 */
const dimensionsReady = ref(false)

const filteredIndices = computed(() => {
  const items = wallItems.value
  const n = items.length
  if (!n) return []
  const q = searchQuery.value.trim()
  if (!q) return items.map((_, i) => i)
  return items
    .map((item, i) => {
      const t = (item.title || item.alt || '').trim()
      return t.includes(q) ? i : -1
    })
    .filter((i) => i >= 0)
})

const hasActiveSearch = computed(() => !!searchQuery.value.trim())

function cardDisplayTitle(item) {
  if (!item) return imageTitlePlaceholder
  const t = (item.title && String(item.title).trim()) || (item.alt && String(item.alt).trim())
  return t || imageTitlePlaceholder
}

const previewIndex = ref(null)
const previewDownloadBusy = ref(false)

const previewImage = computed(() => {
  const i = previewIndex.value
  if (i == null || !wallItems.value[i]) return null
  return wallItems.value[i]
})

let previewKeyHandler = null

function openPreview(i) {
  if (!Number.isFinite(i) || i < 0 || i >= wallItems.value.length) return
  previewIndex.value = i
}

function closePreview() {
  previewIndex.value = null
  previewDownloadBusy.value = false
}

function fileNameFromSrc(src) {
  if (!src || typeof src !== 'string') return 'image'
  try {
    const u = new URL(src, window.location.origin)
    const seg = u.pathname.split('/').filter(Boolean).pop() || 'image'
    return seg.split('?')[0] || 'image'
  } catch {
    return 'image'
  }
}

async function downloadPreviewImage() {
  const item = previewImage.value
  if (!item || previewDownloadBusy.value) return
  previewDownloadBusy.value = true
  const name = fileNameFromSrc(item.src)
  try {
    const res = await fetch(item.src)
    if (!res.ok) throw new Error('fetch failed')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    const a = document.createElement('a')
    a.href = item.src
    a.download = name
    a.target = '_blank'
    a.rel = 'noopener'
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    previewDownloadBusy.value = false
  }
}

watch(previewIndex, (v) => {
  if (previewKeyHandler) {
    window.removeEventListener('keydown', previewKeyHandler)
    previewKeyHandler = null
  }
  if (v !== null) {
    previewKeyHandler = (e) => {
      if (e.key === 'Escape') closePreview()
    }
    window.addEventListener('keydown', previewKeyHandler)
  }
})

let lazyObserver = null
/** 保持对预加载 Image 对象的引用，防止 GC 导致 onload 不触发 */
const _preloadCache = []

function observeLazyMasonryItems() {
  const root = scrollRootRef.value
  if (!root || !lazyObserver) return
  root.querySelectorAll('[data-lazy-index]').forEach((el) => {
    const rawIdx = el.getAttribute('data-lazy-index')
    const idx = rawIdx == null ? NaN : Number(rawIdx)
    if (!Number.isFinite(idx) || loaded[idx]) return
    lazyObserver.observe(el)
  })
}

onMounted(async () => {
  const raw = getImageWallPayload()
  wallItems.value = raw.map((img) => ({
    src: img.src,
    alt: img.alt || '',
    title:
      (img.title && String(img.title).trim()) ||
      (img.alt && String(img.alt).trim()) ||
      fileNameFromSrc(img.src)
  }))

  await Promise.all(
    wallItems.value.map(
      (img, i) =>
        new Promise((resolve) => {
          const el = new Image()
          _preloadCache.push(el)
          el.onload = () => {
            dimensions[i] = { w: el.naturalWidth, h: el.naturalHeight }
            resolve()
          }
          el.onerror = resolve
          el.src = img.src
        })
    )
  )

  dimensionsReady.value = true

  await nextTick()
  const root = scrollRootRef.value
  if (!root || !wallItems.value.length) return

  lazyObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const rawIdx = entry.target.getAttribute('data-lazy-index')
        const idx = rawIdx == null ? NaN : Number(rawIdx)
        if (!Number.isFinite(idx)) continue
        loaded[idx] = true
        lazyObserver.unobserve(entry.target)
      }
    },
    {
      root,
      rootMargin: '320px 0px',
      threshold: 0
    }
  )

  observeLazyMasonryItems()
})

watch([filteredIndices, dimensionsReady], async () => {
  if (!dimensionsReady.value || !lazyObserver) return
  await nextTick()
  observeLazyMasonryItems()
})

onUnmounted(() => {
  if (previewKeyHandler) {
    window.removeEventListener('keydown', previewKeyHandler)
    previewKeyHandler = null
  }
  lazyObserver?.disconnect()
  lazyObserver = null
})

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push({ name: 'Home' })
  }
}
</script>

<style scoped>
.image-wall-page {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  background: var(--color-warm-ivory);
  overflow: hidden;
}

.image-wall-page__close {
  position: absolute;
  top: var(--space-8);
  right: var(--space-10);
  z-index: 50;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(255, 250, 235, 0.94);
  color: var(--color-text-primary);
  cursor: pointer;
  box-shadow:
    rgba(127, 99, 21, 0.16) -2px 4px 14px,
    rgba(127, 99, 21, 0.08) -8px 16px 28px;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.image-wall-page__close:hover {
  background: #fffef8;
  box-shadow:
    rgba(127, 99, 21, 0.22) -2px 4px 14px,
    rgba(127, 99, 21, 0.12) -8px 16px 28px;
}

.image-wall-page__close-icon {
  display: inline-block;
  font-size: 28px;
  line-height: 1;
  font-weight: 300;
  transform: rotate(0deg);
  transform-origin: center;
  transition: transform 0.28s ease;
}

.image-wall-page__close:hover .image-wall-page__close-icon {
  transform: rotate(-90deg);
}

.image-wall-page__main {
  position: relative;
  z-index: 0;
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: var(--space-10) var(--space-10) var(--space-12);
}

.image-wall-page__search-row {
  max-width: 1400px;
  margin: 0 auto var(--space-6);
}

.image-wall-page__search {
  display: block;
  width: 100%;
  max-width: min(100%, 420px);
  margin: 0 auto;
  padding: var(--space-3) var(--space-4);
  font-size: var(--fs-body);
  border: 1px solid rgba(127, 99, 21, 0.2);
  border-radius: var(--radius, 0);
  background: var(--color-white, #fff);
  color: var(--color-text-primary);
  box-sizing: border-box;
}

.image-wall-page__search::placeholder {
  color: var(--color-text-secondary);
}

.image-wall-page__search:focus {
  outline: 2px solid rgba(127, 99, 21, 0.45);
  outline-offset: 2px;
}

/* type=search 内置清除按钮：悬停为手型（WebKit / Chromium） */
.image-wall-page__search::-webkit-search-cancel-button {
  cursor: pointer;
}

.image-wall-page__empty {
  max-width: 480px;
  margin: var(--space-12) auto 0;
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--color-text-secondary);
  text-align: center;
}

.image-wall-page__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: var(--space-12) 0;
}

.image-wall-page__loading-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-secondary, #9b8460);
  opacity: 0.5;
  animation: loading-bounce 1.2s ease-in-out infinite;
}

.image-wall-page__loading-dot:nth-child(1) { animation-delay: 0s; }
.image-wall-page__loading-dot:nth-child(2) { animation-delay: 0.2s; }
.image-wall-page__loading-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes loading-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.3; }
  40%            { transform: scale(1);   opacity: 0.9; }
}

.image-wall-page__masonry {
  max-width: 1400px;
  margin: 0 auto;
  column-count: 2;
  column-gap: var(--space-5);
}

@media (min-width: 768px) {
  .image-wall-page__masonry {
    column-count: 3;
    column-gap: var(--space-6);
  }
}

@media (min-width: 1200px) {
  .image-wall-page__masonry {
    column-count: 4;
  }
}

.image-wall-page__item {
  margin: 0 0 var(--space-5);
  break-inside: avoid;
}

/* 与 TableRowDetailView 封面区一致：外层居中 + 白底衬卡 */
.image-wall-page__cover-wrap {
  display: flex;
  justify-content: center;
  width: 100%;
}

.image-wall-page__cover-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
  max-width: min(100%, 420px);
  padding: var(--space-5) var(--space-6);
  background: var(--color-white, #fff);
  box-shadow: var(--shadow-card);
  border-radius: var(--radius, 0);
}

.image-wall-page__img-wrapper {
  cursor: pointer;
  border-radius: inherit;
}

.image-wall-page__img-wrapper:focus-visible {
  outline: 2px solid rgba(127, 99, 21, 0.55);
  outline-offset: 3px;
}

.image-wall-page__preview-backdrop {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-10);
  padding-top: calc(var(--space-10) + 52px);
  box-sizing: border-box;
  background: rgba(22, 14, 4, 0.92);
  backdrop-filter: blur(8px);
}

.image-wall-page__preview-toolbar {
  position: fixed;
  top: var(--space-8);
  right: var(--space-10);
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.image-wall-page__preview-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  padding: 0;
  border: none;
  border-radius: 0;
  background: #fff0c2;
  color: #1f1f1f;
  box-shadow:
    rgba(127, 99, 21, 0.16) -3px 6px 18px,
    rgba(127, 99, 21, 0.09) -10px 20px 32px;
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.image-wall-page__preview-btn:hover:not(:disabled) {
  background: #ffe295;
  box-shadow:
    rgba(127, 99, 21, 0.22) -3px 6px 18px,
    rgba(127, 99, 21, 0.13) -10px 20px 32px;
}

.image-wall-page__preview-btn:disabled {
  opacity: 0.5;
  cursor: wait;
}

.image-wall-page__preview-btn--download {
  background: #ffa110;
  color: #1f1f1f;
}

.image-wall-page__preview-btn--download:hover:not(:disabled) {
  background: #ffb83e;
}

.image-wall-page__preview-btn-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.image-wall-page__preview-btn-icon--spin {
  animation: preview-spin 0.9s linear infinite;
}

@keyframes preview-spin {
  to { transform: rotate(360deg); }
}

.image-wall-page__preview-stage {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: min(1200px, 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-wall-page__preview-img {
  display: block;
  max-width: 100%;
  max-height: min(88vh, 100%);
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: var(--radius, 4px);
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.35);
}

.image-wall-page__cover-img {
  display: block;
  width: 100%;
  max-width: 100%;
  height: auto;
  vertical-align: top;
}

/* 懒加载前：沿用详情页占位肌理；入场后由 observer 切换为图片 */
.image-wall-page__cover-placeholder {
  width: 100%;
  min-height: 160px;
  background: linear-gradient(
    160deg,
    var(--color-cream, #fff0c2) 0%,
    rgba(255, 250, 235, 0.9) 100%
  );
  border: 1px solid rgba(127, 99, 21, 0.12);
}

.image-wall-page__image-title {
  margin: var(--space-4) 0 0;
  padding: 0;
  width: 100%;
  text-align: center;
  font-size: var(--fs-feature);
  font-weight: 400;
  color: var(--color-text-primary);
  line-height: 1.25;
  letter-spacing: -0.3px;
}
</style>
