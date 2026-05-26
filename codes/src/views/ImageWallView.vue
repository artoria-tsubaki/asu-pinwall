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
        ref="previewBackdropRef"
        class="image-wall-page__preview-backdrop"
        :class="{ 'image-wall-page__preview-backdrop--active': previewBackdropVisible }"
        role="dialog"
        aria-modal="true"
        aria-label="图片预览"
        @click="closePreview"
      >
        <div
          class="image-wall-page__preview-toolbar"
          :class="{ 'image-wall-page__preview-toolbar--active': previewBackdropVisible }"
          @click.stop
        >
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
          <div
            v-if="previewImage"
            ref="previewFrameRef"
            class="image-wall-page__preview-frame"
            :style="previewFrameStyle"
            @click.stop
          >
            <img
              :src="previewImage.src"
              :alt="cardDisplayTitle(previewImage)"
              class="image-wall-page__preview-img"
              decoding="async"
            />
          </div>
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
          placeholder="按标题搜索"
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
          :key="`${i}-${wallItems[i].src}`"
          class="image-wall-page__item"
          :data-lazy-index="i"
        >
          <div class="image-wall-page__cover-wrap">
            <div class="image-wall-page__cover-card">
              <div
                :ref="(el) => setThumbRef(i, el)"
                class="image-wall-page__img-wrapper"
                :class="{ 'image-wall-page__img-wrapper--previewing': i === previewIndex }"
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

import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import asuCoverMusicData from '../../../data/asu_cover_music_data.json'

const imageTitlePlaceholder = '图片标题'
const asuCoverImages = import.meta.glob('../assets/images/asu-cover/*', {
  eager: true,
  import: 'default',
  query: '?url'
})
const asuCoverImageByFile = new Map(
  Object.entries(asuCoverImages).map(([path, src]) => [path.split('/').pop(), src])
)

const router = useRouter()
const wallItems = ref([])
const searchQuery = ref('')
const scrollRootRef = ref(null)
const loaded = reactive({})
const dimensions = reactive({})
const dimensionsReady = ref(false)

const previewIndex = ref(null)
const previewDownloadBusy = ref(false)
const previewBackdropVisible = ref(false)
const previewBackdropRef = ref(null)
const previewFrameRef = ref(null)
const previewAnimating = ref(false)
const previewSourceRect = ref(null)

const viewportSize = reactive({ width: 0, height: 0 })
const thumbRefs = new Map()
const preloadCache = []

let previewKeyHandler = null
let lazyObserver = null
let motionMediaQuery = null
let prefersReducedMotion = false

const filteredIndices = computed(() => {
  const items = wallItems.value
  if (!items.length) return []

  const q = searchQuery.value.trim()
  if (!q) return items.map((_, index) => index)

  return items
    .map((item, index) => {
      const title = (item.title || item.alt || '').trim()
      return title.includes(q) ? index : -1
    })
    .filter((index) => index >= 0)
})

const hasActiveSearch = computed(() => !!searchQuery.value.trim())

const previewImage = computed(() => {
  const index = previewIndex.value
  if (index == null || !wallItems.value[index]) return null
  return wallItems.value[index]
})

const previewFrameStyle = computed(() => {
  const index = previewIndex.value
  if (index == null) return null

  const size = getPreviewFrameSize(index)
  return {
    width: `${size.width}px`,
    height: `${size.height}px`
  }
})

function cardDisplayTitle(item) {
  if (!item) return imageTitlePlaceholder
  const title = (item.title && String(item.title).trim()) || (item.alt && String(item.alt).trim())
  return title || imageTitlePlaceholder
}

function titleBeforeDash(title) {
  const value = String(title || '').trim()
  if (!value) return ''

  return value.split(/\s+-\s*/)[0]?.trim() || value
}

function asuCoverImageSrc(fileName) {
  if (!fileName) return ''

  const targetName = String(fileName).split('/').pop()
  return asuCoverImageByFile.get(targetName) || ''
}

function createAsuCoverWallItems() {
  const discography = Array.isArray(asuCoverMusicData?.discography)
    ? asuCoverMusicData.discography
    : []

  return discography
    .map((item) => {
      const src = asuCoverImageSrc(item?.src)
      const title = titleBeforeDash(item?.Title)

      if (!src) return null

      return {
        src,
        alt: title,
        title
      }
    })
    .filter(Boolean)
}

function setThumbRef(index, el) {
  if (el) {
    thumbRefs.set(index, el)
  } else {
    thumbRefs.delete(index)
  }
}

function updateViewportSize() {
  viewportSize.width = window.innerWidth || document.documentElement.clientWidth || 0
  viewportSize.height = window.innerHeight || document.documentElement.clientHeight || 0
}

function updateReducedMotionPreference() {
  prefersReducedMotion = !!motionMediaQuery?.matches
}

function getPreviewFrameSize(index) {
  const dims = dimensions[index]
  const viewportWidth = Math.max(viewportSize.width || window.innerWidth || 0, 320)
  const viewportHeight = Math.max(viewportSize.height || window.innerHeight || 0, 320)
  const maxWidth = Math.max(Math.min(1200, viewportWidth - 48), 220)
  const maxHeight = Math.max(viewportHeight - 128, 220)

  if (!dims?.w || !dims?.h) {
    const width = maxWidth
    return {
      width: Math.round(width),
      height: Math.round(Math.min(maxHeight, width / 1.5))
    }
  }

  const scale = Math.min(maxWidth / dims.w, maxHeight / dims.h)
  return {
    width: Math.max(1, Math.round(dims.w * scale)),
    height: Math.max(1, Math.round(dims.h * scale))
  }
}

function getRectDelta(fromRect, toRect) {
  if (!fromRect || !toRect || !fromRect.width || !fromRect.height || !toRect.width || !toRect.height) {
    return null
  }

  return {
    x: fromRect.left - toRect.left,
    y: fromRect.top - toRect.top,
    scaleX: fromRect.width / toRect.width,
    scaleY: fromRect.height / toRect.height
  }
}

function waitForNextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

function waitForTransitionEnd(el, fallbackMs = 420) {
  return new Promise((resolve) => {
    if (!el) {
      resolve()
      return
    }

    let done = false
    const finish = () => {
      if (done) return
      done = true
      el.removeEventListener('transitionend', onEnd)
      window.clearTimeout(timer)
      resolve()
    }
    const onEnd = (event) => {
      if (event.target === el) finish()
    }
    const timer = window.setTimeout(finish, fallbackMs)

    el.addEventListener('transitionend', onEnd)
  })
}

function resetPreviewFrameStyle(frameEl = previewFrameRef.value) {
  if (!frameEl) return
  frameEl.style.transition = ''
  frameEl.style.transform = ''
  frameEl.style.transformOrigin = ''
}

async function runPreviewOpenAnimation() {
  const frameEl = previewFrameRef.value
  const delta = getRectDelta(previewSourceRect.value, frameEl?.getBoundingClientRect())

  if (!frameEl || prefersReducedMotion || !delta) {
    previewBackdropVisible.value = true
    previewAnimating.value = false
    resetPreviewFrameStyle(frameEl)
    return
  }

  previewAnimating.value = true
  frameEl.style.transformOrigin = 'top left'
  frameEl.style.transition = 'none'
  frameEl.style.transform = `translate(${delta.x}px, ${delta.y}px) scale(${delta.scaleX}, ${delta.scaleY})`

  await waitForNextFrame()

  previewBackdropVisible.value = true
  frameEl.style.transition = 'transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1)'
  frameEl.style.transform = 'translate(0px, 0px) scale(1, 1)'

  await waitForTransitionEnd(frameEl)
  resetPreviewFrameStyle(frameEl)
  previewAnimating.value = false
}

async function runPreviewCloseAnimation() {
  const frameEl = previewFrameRef.value
  const targetThumbEl = thumbRefs.get(previewIndex.value)
  const delta = getRectDelta(targetThumbEl?.getBoundingClientRect(), frameEl?.getBoundingClientRect())

  previewBackdropVisible.value = false

  if (!frameEl || prefersReducedMotion || !delta) {
    previewAnimating.value = false
    previewIndex.value = null
    previewDownloadBusy.value = false
    resetPreviewFrameStyle(frameEl)
    return
  }

  previewAnimating.value = true
  frameEl.style.transformOrigin = 'top left'
  frameEl.style.transition = 'transform 0.32s cubic-bezier(0.4, 0, 0.2, 1)'
  frameEl.style.transform = `translate(${delta.x}px, ${delta.y}px) scale(${delta.scaleX}, ${delta.scaleY})`

  await waitForTransitionEnd(frameEl, 380)
  resetPreviewFrameStyle(frameEl)
  previewAnimating.value = false
  previewIndex.value = null
  previewDownloadBusy.value = false
}

async function openPreview(index) {
  if (
    !Number.isFinite(index) ||
    index < 0 ||
    index >= wallItems.value.length ||
    previewAnimating.value ||
    previewIndex.value !== null
  ) {
    return
  }

  previewSourceRect.value = thumbRefs.get(index)?.getBoundingClientRect() || null
  previewIndex.value = index
  previewBackdropVisible.value = false
  previewDownloadBusy.value = false

  await nextTick()
  await waitForNextFrame()
  await runPreviewOpenAnimation()
}

async function closePreview() {
  if (previewIndex.value === null || previewAnimating.value) return
  await runPreviewCloseAnimation()
}

function fileNameFromSrc(src) {
  if (!src || typeof src !== 'string') return 'image'
  try {
    const url = new URL(src, window.location.origin)
    const segment = url.pathname.split('/').filter(Boolean).pop() || 'image'
    return segment.split('?')[0] || 'image'
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
    const response = await fetch(item.src)
    if (!response.ok) throw new Error('fetch failed')

    const blob = await response.blob()
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

function observeLazyMasonryItems() {
  const root = scrollRootRef.value
  if (!root || !lazyObserver) return

  root.querySelectorAll('[data-lazy-index]').forEach((el) => {
    const rawIndex = el.getAttribute('data-lazy-index')
    const index = rawIndex == null ? NaN : Number(rawIndex)
    if (!Number.isFinite(index) || loaded[index]) return
    lazyObserver.observe(el)
  })
}

watch(previewIndex, (value) => {
  if (previewKeyHandler) {
    window.removeEventListener('keydown', previewKeyHandler)
    previewKeyHandler = null
  }

  if (value !== null) {
    previewKeyHandler = (event) => {
      if (event.key === 'Escape') closePreview()
    }
    window.addEventListener('keydown', previewKeyHandler)
  }
})

watch([filteredIndices, dimensionsReady], async () => {
  if (!dimensionsReady.value || !lazyObserver) return
  await nextTick()
  observeLazyMasonryItems()
})

onMounted(async () => {
  updateViewportSize()
  window.addEventListener('resize', updateViewportSize)

  motionMediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  updateReducedMotionPreference()
  motionMediaQuery.addEventListener?.('change', updateReducedMotionPreference)

  wallItems.value = createAsuCoverWallItems()

  await Promise.all(
    wallItems.value.map(
      (img, index) =>
        new Promise((resolve) => {
          const image = new Image()
          preloadCache.push(image)
          image.onload = () => {
            dimensions[index] = { w: image.naturalWidth, h: image.naturalHeight }
            resolve()
          }
          image.onerror = resolve
          image.src = img.src
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

        const rawIndex = entry.target.getAttribute('data-lazy-index')
        const index = rawIndex == null ? NaN : Number(rawIndex)
        if (!Number.isFinite(index)) continue

        loaded[index] = true
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

onUnmounted(() => {
  if (previewKeyHandler) {
    window.removeEventListener('keydown', previewKeyHandler)
    previewKeyHandler = null
  }

  window.removeEventListener('resize', updateViewportSize)
  motionMediaQuery?.removeEventListener?.('change', updateReducedMotionPreference)
  motionMediaQuery = null

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

.image-wall-page__loading-dot:nth-child(1) {
  animation-delay: 0s;
}

.image-wall-page__loading-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.image-wall-page__loading-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes loading-bounce {
  0%,
  80%,
  100% {
    transform: scale(0.6);
    opacity: 0.3;
  }

  40% {
    transform: scale(1);
    opacity: 0.9;
  }
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
  overflow: hidden;
  transition: opacity 0.18s ease;
}

.image-wall-page__img-wrapper--previewing {
  opacity: 0;
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
  opacity: 0;
  transition: opacity 0.26s ease;
}

.image-wall-page__preview-backdrop--active {
  opacity: 1;
}

.image-wall-page__preview-toolbar {
  position: fixed;
  top: var(--space-8);
  right: var(--space-10);
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--space-4);
  opacity: 0;
  transform: translateY(-10px);
  transition: opacity 0.24s ease, transform 0.24s ease;
}

.image-wall-page__preview-toolbar--active {
  opacity: 1;
  transform: translateY(0);
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
  to {
    transform: rotate(360deg);
  }
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

.image-wall-page__preview-frame {
  position: relative;
  flex: 0 0 auto;
  max-width: 100%;
  max-height: min(88vh, 100%);
  will-change: transform;
}

.image-wall-page__preview-img {
  display: block;
  width: 100%;
  height: 100%;
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

@media (prefers-reduced-motion: reduce) {
  .image-wall-page__img-wrapper,
  .image-wall-page__preview-backdrop,
  .image-wall-page__preview-toolbar,
  .image-wall-page__preview-btn,
  .image-wall-page__close-icon {
    transition: none;
  }
}
</style>
