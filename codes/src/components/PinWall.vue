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
      <div class="pin-wall__brand">
        <span class="pin-wall__brand-block"></span>
        <h1 class="pin-wall__title">PIN WALL</h1>
      </div>
      <div class="pin-wall__header-right">
        <p class="pin-wall__subtitle">图钉墙 · 创意空间</p>
        <span class="pin-wall__hint">按住鼠标拖动画布</span>
      </div>
    </header>

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
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
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
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.pin-wall__subtitle {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  letter-spacing: 0.5px;
}

.pin-wall__hint {
  font-size: 11px;
  color: rgba(127, 99, 21, 0.5);
  letter-spacing: 0.3px;
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
