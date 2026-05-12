<template>
  <!-- 视口容器：固定大小，不溢出 -->
  <div
    class="pin-viewport"
    ref="viewportRef"
    :class="{ 'pin-viewport--dragging': isDragging, 'pin-viewport--loading': !cardsReady }"
    :aria-busy="!cardsReady"
    @mousedown="onMouseDown"
    @mousemove="onMouseMove"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp"
    @wheel.prevent="onWheel"
  >
    <SvgMouseFollower />
    <!-- 固定的标题栏（在 viewport 上层，不随画布移动） -->
    <header class="pin-wall__header">
      <div class="pin-wall__header-start">
        <div class="pin-wall__brand">
          <span class="pin-wall__brand-block"></span>
          <h1 class="pin-wall__title">PIN WALL</h1>
        </div>
      </div>
      <div class="pin-wall__header-right">
        <button
          type="button"
          class="pin-wall__nav-open"
          aria-label="打开导航菜单"
          :aria-expanded="drawerOpen"
          @click="openDrawer"
        >
          <span class="pin-wall__nav-open-bars" aria-hidden="true">
            <span class="pin-wall__nav-open-bar" />
            <span class="pin-wall__nav-open-bar" />
            <span class="pin-wall__nav-open-bar" />
          </span>
          <span class="pin-wall__nav-open-label">导航</span>
        </button>
      </div>
    </header>

    <Teleport to="body">
      <Transition name="pin-wall-drawer">
        <div
          v-if="drawerOpen"
          class="pin-wall-drawer"
          role="presentation"
        >
          <div
            class="pin-wall-drawer__backdrop"
            aria-hidden="true"
            @click="closeDrawer"
          />
          <aside
            class="pin-wall-drawer__panel"
            role="dialog"
            aria-modal="true"
            aria-label="卡片导航"
            @click.stop
          >
            <div class="pin-wall-drawer__head">
              <span class="pin-wall-drawer__head-title">卡片</span>
              <button
                type="button"
                class="pin-wall-drawer__close"
                aria-label="关闭导航菜单"
                @click="closeDrawer"
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>
            <nav class="pin-wall-drawer__nav" aria-label="画布卡片列表">
              <button
                v-for="(card, idx) in props.cards"
                :key="card.id"
                type="button"
                class="pin-wall-drawer__item"
                :class="{
                  'pin-wall-drawer__item--odd': idx % 2 === 0,
                  'pin-wall-drawer__item--even': idx % 2 === 1
                }"
                :style="{ '--drawer-i': idx }"
                @click="onDrawerNavigate(card)"
              >
                {{ navLabel(card) }}
              </button>
            </nav>
          </aside>
        </div>
      </Transition>
    </Teleport>

    <!-- 卡片内图片等资源就绪前的加载层 -->
    <div
      v-show="!cardsReady"
      class="pin-wall__loading"
      aria-live="polite"
      aria-label="正在加载卡片资源"
    >
      <div class="pin-wall__loading-inner">
        <div class="pin-wall__loading-spinner" aria-hidden="true"></div>
        <p class="pin-wall__loading-text">正在加载卡片资源…</p>
      </div>
    </div>

    <!-- 图钉墙预览组件（左上角悬浮，等卡片渲染完成后再挂载） -->
    <PinWallPreview
      v-if="cardsReady"
      :cards="cards"
      :cardDimensions="cardDimensions"
      :offsetX="offsetX"
      :offsetY="offsetY"
      :viewportWidth="viewportWidth"
      :viewportHeight="viewportHeight"
      :canvasWidth="CANVAS_W"
      :canvasHeight="CANVAS_H"
      @navigate="onNavigate"
    />

    <!-- 可无限拖拽的画布 -->
    <div
      class="pin-wall__canvas"
      :class="{ 'pin-wall__canvas--navigating': isNavigating }"
      :style="{
        transform: `translate(${offsetX}px, ${offsetY}px)`,
        width: CANVAS_W + 'px',
        height: CANVAS_H + 'px'
      }"
    >
      <!-- 装饰性座标纸纹理（随画布移动） -->
      <div class="pin-wall__canvas-bg"></div>

      <PinCard
        v-for="card in cards"
        :key="card.id"
        :ref="el => collectCardRef(card.id, el)"
        :card="card"
        :style="{
          position: 'absolute',
          left: card.x + 'px',
          top: card.y + 'px',
          transform: `rotate(${card.rotate || 0}deg)`,
          zIndex: card.zIndex || 1
        }"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import PinCard from './PinCard.vue'
import PinWallPreview from './PinWallPreview.vue'
import SvgMouseFollower from './SvgMouseFollower.vue'

const props = defineProps({
  cards: {
    type: Array,
    default: () => []
  }
})

// 画布尺寸：视口约 1920×1080，扩大一倍
const CANVAS_W = 3840
const CANVAS_H = 2400

const viewportRef = ref(null)

// 预览组件渲染控制：等卡片 DOM 就绪后再挂载预览组件
const cardsReady = ref(false)
const cardDimensions = ref({})

// 收集各 PinCard 组件实例（v-for 中使用回调 ref）
const _cardRefs = {}
function collectCardRef(cardId, el) {
  if (el) _cardRefs[cardId] = el
  else delete _cardRefs[cardId]
}

// 画布偏移量（初始居中展示）
const offsetX = ref(0)
const offsetY = ref(0)

// 视口尺寸（实时更新，用于传递给预览组件）
const viewportWidth = ref(window.innerWidth)
const viewportHeight = ref(window.innerHeight)

// 导航动画状态
const isNavigating = ref(false)
let navigatingTimer = null

// 拖拽状态
const isDragging = ref(false)
let startX = 0
let startY = 0
let startOffsetX = 0
let startOffsetY = 0

/** 顶部导航抽屉：按卡片标题跳转画布（与 PinWallPreview 中线对齐逻辑一致） */
const drawerOpen = ref(false)
let drawerEscapeHandler = null

const PIN_STACK_ABOVE_CARD = 28
const DEFAULT_LAYOUT_BY_TYPE = {
  text: { w: 300, h: 248 },
  image: { w: 400, h: 312 },
  video: { w: 380, h: 268 },
  table: { w: 360, h: 228 },
  mixed: { w: 400, h: 292 },
  profile: { w: 320, h: 420 },
  'social-grid': { w: 360, h: 200 },
  days: { w: 300, h: 400 },
  tweets: { w: 440, h: 420 },
  'image-wall-teaser': { w: 420, h: 480 }
}
const DEFAULT_LAYOUT_FALLBACK = { w: 320, h: 240 }

function navLabel(card) {
  const t = card.title
  if (t != null && String(t).trim() !== '') return String(t).trim()
  if (card.content?.sectionLabel) return card.content.sectionLabel
  if (card.type === 'social-grid') return '社交链接'
  return card.id || '未命名'
}

function getCardLayoutSizeForNav(card) {
  const measured = cardDimensions.value[card.id]
  if (measured && measured.w > 0 && measured.h > 0) {
    return { w: measured.w, h: measured.h }
  }
  if (card.layout && typeof card.layout.w === 'number' && typeof card.layout.h === 'number') {
    return { w: card.layout.w, h: card.layout.h }
  }
  return DEFAULT_LAYOUT_BY_TYPE[card.type] || DEFAULT_LAYOUT_FALLBACK
}

function navigateToCard(card) {
  const vw = viewportWidth.value
  const vh = viewportHeight.value - 64
  const pinStack = card.type === 'social-grid' ? 0 : PIN_STACK_ABOVE_CARD
  const { w, h } = getCardLayoutSizeForNav(card)
  const centerCanvasX = card.x + w / 2
  const centerCanvasY = card.y + pinStack + h / 2
  const targetOffsetX = -(centerCanvasX - vw / 2)
  const targetOffsetY = -(centerCanvasY - vh / 2)
  onNavigate(targetOffsetX, targetOffsetY)
}

function openDrawer() {
  drawerOpen.value = true
}

function closeDrawer() {
  drawerOpen.value = false
}

function onDrawerNavigate(card) {
  closeDrawer()
  nextTick(() => navigateToCard(card))
}

watch(drawerOpen, (open) => {
  if (drawerEscapeHandler) {
    document.removeEventListener('keydown', drawerEscapeHandler)
    drawerEscapeHandler = null
  }
  if (open) {
    drawerEscapeHandler = (e) => {
      if (e.key === 'Escape') closeDrawer()
    }
    document.addEventListener('keydown', drawerEscapeHandler)
  }
})

onUnmounted(() => {
  if (drawerEscapeHandler) {
    document.removeEventListener('keydown', drawerEscapeHandler)
    drawerEscapeHandler = null
  }
})

// 初始化时将画布定位到左上角（留出 header 高度）
onMounted(async () => {
  offsetX.value = 0
  offsetY.value = 0

  const handleResize = () => {
    viewportWidth.value = viewportRef.value?.clientWidth || window.innerWidth
    viewportHeight.value = viewportRef.value?.clientHeight || window.innerHeight
  }
  window.addEventListener('resize', handleResize)
  handleResize()

  // 等卡片全部渲染完毕
  await nextTick()

  // 收集所有卡片内尚未加载完成的图片，等待它们全部就绪（load 或 error）
  const imgPromises = []
  for (const card of props.cards) {
    const compEl = _cardRefs[card.id]
    if (compEl?.$el) {
      compEl.$el.querySelectorAll('img').forEach(img => {
        if (!img.complete) {
          imgPromises.push(new Promise(resolve => {
            img.addEventListener('load', resolve, { once: true })
            img.addEventListener('error', resolve, { once: true })
          }))
        }
      })
    }
  }
  await Promise.all(imgPromises)

  // 图片全部就绪后，读取每张卡片的真实宽高
  const dims = {}
  for (const card of props.cards) {
    const compEl = _cardRefs[card.id]
    if (compEl?.$el) {
      const cardEl = compEl.$el.querySelector('.pin-card, .social-grid')
      if (cardEl) {
        dims[card.id] = { w: cardEl.offsetWidth, h: cardEl.offsetHeight }
      }
    }
  }
  cardDimensions.value = dims
  cardsReady.value = true

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
    if (navigatingTimer) clearTimeout(navigatingTimer)
  })
})

// 处理来自预览组件的导航事件（带平滑过渡动画）
function onNavigate(targetX, targetY) {
  isNavigating.value = true
  if (navigatingTimer) clearTimeout(navigatingTimer)

  offsetX.value = clampOffset(targetX, 'x')
  offsetY.value = clampOffset(targetY, 'y')

  navigatingTimer = setTimeout(() => {
    isNavigating.value = false
  }, 550)
}

function onMouseDown(e) {
  // 只响应左键，且不在卡片内部启动（避免阻断卡片内部的链接、按钮等交互）
  if (e.button !== 0) return
  // 如果点击来源是卡片内部的交互元素则跳过
  if (e.target.closest('.pin-card') || e.target.closest('.social-grid')) return
  isDragging.value = true
  startX = e.clientX
  startY = e.clientY
  startOffsetX = offsetX.value
  startOffsetY = offsetY.value
  e.preventDefault()
}

function onMouseMove(e) {
  if (!isDragging.value) return
  const dx = e.clientX - startX
  const dy = e.clientY - startY
  offsetX.value = clampOffset(startOffsetX + dx, 'x')
  offsetY.value = clampOffset(startOffsetY + dy, 'y')
}

function onMouseUp() {
  isDragging.value = false
}

function onWheel(e) {
  // 滚轮也可以平移（不缩放）
  offsetX.value = clampOffset(offsetX.value - e.deltaX, 'x')
  offsetY.value = clampOffset(offsetY.value - e.deltaY, 'y')
}

function clampOffset(val, axis) {
  const vw = viewportRef.value?.clientWidth || window.innerWidth
  const vh = viewportRef.value?.clientHeight || window.innerHeight
  const headerH = 64
  if (axis === 'x') {
    // 不能超出右边（画布左侧不能滚出去太多）
    const max = 0
    const min = -(CANVAS_W - vw)
    return Math.min(max, Math.max(min, val))
  } else {
    const max = -headerH
    const min = -(CANVAS_H - vh + headerH)
    return Math.min(0, Math.max(min, val))
  }
}
</script>

<style scoped>
/* ---- 视口：固定满屏，不滚动 ---- */
.pin-viewport {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background-color: var(--color-warm-ivory);
  cursor: grab;
  user-select: none;
}

.pin-viewport--dragging {
  cursor: grabbing;
}

.pin-viewport--loading {
  cursor: wait;
}

/* ---- 资源加载层（卡片图片等就绪前） ---- */
.pin-wall__loading {
  position: absolute;
  top: 64px;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 90;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 250, 235, 0.82);
  backdrop-filter: blur(6px);
  pointer-events: auto;
}

.pin-wall__loading-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.pin-wall__loading-spinner {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: 2px solid rgba(127, 99, 21, 0.2);
  border-top-color: var(--color-brand-orange);
  animation: pin-wall-loading-spin 0.75s linear infinite;
}

.pin-wall__loading-text {
  margin: 0;
  font-family: var(--font-family);
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 0.4px;
  color: rgba(31, 31, 31, 0.55);
}

@keyframes pin-wall-loading-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---- 固定标题栏 ---- */
.pin-wall__header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  height: 64px;
  padding: 0 var(--space-12);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 250, 235, 0.9);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(127, 99, 21, 0.12);
  pointer-events: none;
}

.pin-wall__brand {
  display: flex;
  align-items: center;
  gap: var(--space-6);
}

.pin-wall__brand-block {
  display: inline-block;
  width: 28px;
  height: 28px;
  background: var(--gradient-mistral-block);
  flex-shrink: 0;
}

.pin-wall__title {
  font-family: var(--font-family);
  font-size: var(--fs-subheading);
  font-weight: 400;
  letter-spacing: -1px;
  color: var(--color-mistral-black);
  line-height: 1;
}

.pin-wall__header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  pointer-events: auto;
}

.pin-wall__header-start {
  display: flex;
  align-items: center;
  pointer-events: auto;
}

.pin-wall__nav-open {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 14px;
  border: none;
  border-radius: 0;
  background: #fff0c2;
  color: #1f1f1f;
  cursor: pointer;
  font-family: var(--font-family);
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  box-shadow:
    rgba(127, 99, 21, 0.14) -2px 4px 12px,
    rgba(127, 99, 21, 0.06) -6px 12px 24px;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.pin-wall__nav-open:hover {
  background: #ffe295;
  box-shadow:
    rgba(127, 99, 21, 0.2) -2px 4px 12px,
    rgba(127, 99, 21, 0.1) -6px 12px 24px;
}

.pin-wall__nav-open-bars {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pin-wall__nav-open-bar {
  display: block;
  width: 18px;
  height: 2px;
  background: #1f1f1f;
}

@media (max-width: 520px) {
  .pin-wall__nav-open-label {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .pin-wall__nav-open {
    padding: 0 12px;
  }
}

/* ---- 顶部导航抽屉 ---- */
.pin-wall-drawer {
  position: fixed;
  inset: 0;
  z-index: 120;
  pointer-events: none;
}

.pin-wall-drawer__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(22, 14, 4, 0.42);
  backdrop-filter: blur(5px);
  pointer-events: auto;
}

.pin-wall-drawer__panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(380px, 90vw);
  background: #fffaeb;
  border-left: 1px solid rgba(127, 99, 21, 0.18);
  box-shadow:
    rgba(127, 99, 21, 0.12) -10px 0 36px,
    rgba(127, 99, 21, 0.08) -24px 0 64px;
  pointer-events: auto;
  display: flex;
  flex-direction: column;
  border-radius: 0;
}

.pin-wall-drawer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px 0 20px;
  border-bottom: 1px solid rgba(127, 99, 21, 0.12);
  flex-shrink: 0;
}

.pin-wall-drawer__head-title {
  font-family: var(--font-family);
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(31, 31, 31, 0.45);
}

.pin-wall-drawer__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  color: #1f1f1f;
  font-size: 24px;
  line-height: 1;
  font-weight: 400;
  cursor: pointer;
  transition: background 0.15s ease;
}

.pin-wall-drawer__close:hover {
  background: rgba(127, 99, 21, 0.08);
}

.pin-wall-drawer__nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 0 24px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pin-wall-drawer__item {
  display: block;
  width: 100%;
  margin: 0;
  padding: 14px 24px;
  border: none;
  border-radius: 0;
  background: transparent;
  font-family: var(--font-family);
  font-size: 17px;
  font-weight: 400;
  line-height: 1.25;
  letter-spacing: -0.02em;
  color: #1f1f1f;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease;
  opacity: 0;
  animation-duration: 0.52s;
  animation-timing-function: cubic-bezier(0.22, 1, 0.36, 1);
  animation-fill-mode: forwards;
  animation-delay: calc(var(--drawer-i, 0) * 56ms + 80ms);
}

.pin-wall-drawer__item--odd {
  animation-name: pin-wall-drawer-item-in-from-right;
}

.pin-wall-drawer__item--even {
  animation-name: pin-wall-drawer-item-in-from-left;
}

.pin-wall-drawer__item:hover {
  background: rgba(255, 240, 194, 0.85);
}

.pin-wall-drawer__item:active {
  background: rgba(255, 217, 0, 0.2);
}

@keyframes pin-wall-drawer-item-in-from-left {
  from {
    opacity: 0;
    transform: translateX(-36px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes pin-wall-drawer-item-in-from-right {
  from {
    opacity: 0;
    transform: translateX(36px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.pin-wall-drawer-enter-active .pin-wall-drawer__backdrop,
.pin-wall-drawer-leave-active .pin-wall-drawer__backdrop {
  transition: opacity 0.32s ease;
}

.pin-wall-drawer-enter-active .pin-wall-drawer__panel,
.pin-wall-drawer-leave-active .pin-wall-drawer__panel {
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.pin-wall-drawer-enter-from .pin-wall-drawer__backdrop,
.pin-wall-drawer-leave-to .pin-wall-drawer__backdrop {
  opacity: 0;
}

.pin-wall-drawer-enter-from .pin-wall-drawer__panel,
.pin-wall-drawer-leave-to .pin-wall-drawer__panel {
  transform: translateX(100%);
}

/* ---- 画布（可拖拽移动） ---- */
.pin-wall__canvas {
  position: absolute;
  top: 64px; /* header 高度 */
  left: 0;
  will-change: transform;
  transform-origin: 0 0;
  transition: none;
}

/* 导航时启用平滑过渡 */
.pin-wall__canvas--navigating {
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 画布背景纹理（随画布走） */
.pin-wall__canvas-bg {
  position: absolute;
  inset: 0;
  background-image:
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 28px,
      rgba(127, 99, 21, 0.035) 28px,
      rgba(127, 99, 21, 0.035) 29px
    ),
    repeating-linear-gradient(
      90deg,
      transparent,
      transparent 28px,
      rgba(127, 99, 21, 0.035) 28px,
      rgba(127, 99, 21, 0.035) 29px
    );
  pointer-events: none;
}
</style>
