<template>
  <div class="preview-panel" :class="{ 'preview-panel--collapsed': collapsed }">
    <!-- 顶部栏 -->
    <div class="preview-top">
      <!-- 折叠按钮 -->
      <button class="preview-btn preview-btn--collapse" @click="collapsed = !collapsed" :title="collapsed ? '展开预览' : '折叠预览'">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path
            v-if="collapsed"
            d="M2 3.5L5 6.5L8 3.5"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="square"
          />
          <path
            v-else
            d="M2 6.5L5 3.5L8 6.5"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="square"
          />
        </svg>
      </button>

      <!-- 面包屑路径 -->
      <div class="preview-breadcrumb">
        <span class="preview-breadcrumb__root">PIN WALL</span>
        <span class="preview-breadcrumb__sep">/</span>
        <span class="preview-breadcrumb__current">{{ currentSection.label }}</span>
      </div>

      <!-- 箭头导航（Finder 风格前进/后退） -->
      <div class="preview-nav">
        <button class="preview-btn preview-btn--nav" @click="navigatePrev" title="后退">
          <svg width="8" height="10" viewBox="0 0 8 10" fill="none">
            <path d="M6 1L2 5L6 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"/>
          </svg>
        </button>
        <button class="preview-btn preview-btn--nav" @click="navigateNext" title="前进">
          <svg width="8" height="10" viewBox="0 0 8 10" fill="none">
            <path d="M2 1L6 5L2 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="square"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 主体 Minimap（可折叠） -->
    <div class="preview-body" v-show="!collapsed">
      <div
        class="minimap"
        :style="{ width: MINIMAP_W + 'px', height: MINIMAP_H + 'px' }"
        @click="onMinimapClick"
      >
        <!-- 画布白色背景 -->
        <div class="minimap__canvas-bg"></div>

        <!-- 四象限分割线 -->
        <div class="minimap__divider-v"></div>
        <div class="minimap__divider-h"></div>

        <!-- 四象限标签 -->
        <span class="minimap__label minimap__label--tl">INFORMATION</span>
        <span class="minimap__label minimap__label--tr">MUSIC</span>
        <span class="minimap__label minimap__label--bl">CAREER</span>
        <span class="minimap__label minimap__label--br">NEWS</span>

        <!-- 卡片方块 -->
        <div
          v-for="card in cards"
          :key="card.id"
          class="minimap__card"
          :style="cardBlockStyle(card)"
          :title="card.title"
        ></div>

        <!-- 当前视口指示框 -->
        <div class="minimap__viewport" :style="viewportStyle"></div>
      </div>

      <!-- 区域指示点 -->
      <div class="preview-sections">
        <button
          v-for="(section, idx) in sections"
          :key="section.id"
          class="preview-section-dot"
          :class="{ 'preview-section-dot--active': idx === currentSectionIndex }"
          @click="navigateTo(section)"
          :title="section.label"
        ></button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  cards: {
    type: Array,
    default: () => []
  },
  // 各卡片的真实 DOM 尺寸（由父组件在卡片渲染后测量传入）
  cardDimensions: {
    type: Object,
    default: () => ({})
  },
  offsetX: {
    type: Number,
    default: 0
  },
  offsetY: {
    type: Number,
    default: 0
  },
  viewportWidth: {
    type: Number,
    default: 1920
  },
  viewportHeight: {
    type: Number,
    default: 1080
  },
  canvasWidth: {
    type: Number,
    default: 3840
  },
  canvasHeight: {
    type: Number,
    default: 2400
  }
})

const emit = defineEmits(['navigate'])

// 折叠状态
const collapsed = ref(false)

// Minimap 尺寸：使用单一 scale，确保 XY 方向无拉伸
const MINIMAP_W = 340
const scale = MINIMAP_W / props.canvasWidth          // 统一缩放比，约 0.08854
const MINIMAP_H = Math.round(props.canvasHeight * scale) // ≈ 212，与 scale 精确对应

// 四个区域定义（导航顺序：Information → Music → Career → News）
const sections = [
  {
    id: 'information',
    label: 'INFORMATION',
    targetOffsetX: 0,
    targetOffsetY: 0,
    centerX: props.canvasWidth * 0.25,
    centerY: props.canvasHeight * 0.25
  },
  {
    id: 'music',
    label: 'MUSIC',
    targetOffsetX: -(props.canvasWidth / 2),
    targetOffsetY: 0,
    centerX: props.canvasWidth * 0.75,
    centerY: props.canvasHeight * 0.25
  },
  {
    id: 'career',
    label: 'CAREER',
    targetOffsetX: 0,
    targetOffsetY: -(props.canvasHeight / 2),
    centerX: props.canvasWidth * 0.25,
    centerY: props.canvasHeight * 0.75
  },
  {
    id: 'news',
    label: 'NEWS',
    targetOffsetX: -(props.canvasWidth / 2),
    targetOffsetY: -(props.canvasHeight / 2),
    centerX: props.canvasWidth * 0.75,
    centerY: props.canvasHeight * 0.75
  }
]

// 根据当前 offset 计算视口中心点在画布上的位置，判断当前所在象限
const currentSectionIndex = computed(() => {
  const centerCanvasX = -props.offsetX + props.viewportWidth / 2
  const centerCanvasY = -props.offsetY + (props.viewportHeight - 64) / 2
  const halfW = props.canvasWidth / 2
  const halfH = props.canvasHeight / 2
  if (centerCanvasX < halfW && centerCanvasY < halfH) return 0  // Information
  if (centerCanvasX >= halfW && centerCanvasY < halfH) return 1  // Music
  if (centerCanvasX < halfW && centerCanvasY >= halfH) return 2  // Career
  return 3  // News
})

const currentSection = computed(() => sections[currentSectionIndex.value])

// 视口指示框样式（统一使用 scale，XY 无拉伸）
const viewportStyle = computed(() => {
  const vw = props.viewportWidth
  const vh = props.viewportHeight - 64  // 去掉 header 高度
  return {
    left: (-props.offsetX * scale) + 'px',
    top: (-props.offsetY * scale) + 'px',
    width: Math.min(vw * scale, MINIMAP_W) + 'px',
    height: Math.min(vh * scale, MINIMAP_H) + 'px'
  }
})

// 图钉 + 细杆高度：与 PinCard 中 .pin(18) + .pin__stem(10) 一致，白卡片顶边相对 wrapper 的偏移
const PIN_STACK_ABOVE_CARD = 28

// 无 layout 时的默认尺寸：接近 PinCard（min-width 240、内容区典型比例）
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

// 卡片方块样式（各类型用不同暖色区分；长宽与数据 layout 或类型默认一致，保持与真实卡片长宽比接近）
const typeColorMap = {
  text: 'rgba(250, 82, 15, 0.55)',
  image: 'rgba(255, 161, 16, 0.6)',
  video: 'rgba(255, 129, 5, 0.6)',
  table: 'rgba(255, 184, 62, 0.65)',
  mixed: 'rgba(251, 100, 36, 0.55)',
  profile: 'rgba(255, 161, 16, 0.55)',
  'social-grid': 'rgba(255, 217, 0, 0.6)',
  days: 'rgba(250, 82, 15, 0.6)',
  tweets: 'rgba(251, 100, 36, 0.55)',
  'image-wall-teaser': 'rgba(232, 160, 74, 0.58)'
}

function getCardLayoutSize(card) {
  // 优先使用父组件实测的真实 DOM 尺寸
  const measured = props.cardDimensions[card.id]
  if (measured && measured.w > 0 && measured.h > 0) {
    return { w: measured.w, h: measured.h }
  }
  // 次选：数据中声明的 layout 尺寸
  if (card.layout && typeof card.layout.w === 'number' && typeof card.layout.h === 'number') {
    return { w: card.layout.w, h: card.layout.h }
  }
  return DEFAULT_LAYOUT_BY_TYPE[card.type] || DEFAULT_LAYOUT_FALLBACK
}

function cardBlockStyle(card) {
  const { w, h } = getCardLayoutSize(card)
  const pinStack = card.type === 'social-grid' ? 0 : PIN_STACK_ABOVE_CARD
  return {
    left: (card.x * scale) + 'px',
    top: ((card.y + pinStack) * scale) + 'px',
    width: Math.max(w * scale, 4) + 'px',
    height: Math.max(h * scale, 3) + 'px',
    background: typeColorMap[card.type] || 'rgba(255, 161, 16, 0.5)',
    transform: `rotate(${(card.rotate || 0) * 0.3}deg)`
  }
}

// 导航函数
function navigateTo(section) {
  emit('navigate', section.targetOffsetX, section.targetOffsetY)
}

function navigateNext() {
  const nextIdx = (currentSectionIndex.value + 1) % sections.length
  navigateTo(sections[nextIdx])
}

function navigatePrev() {
  const prevIdx = (currentSectionIndex.value - 1 + sections.length) % sections.length
  navigateTo(sections[prevIdx])
}

// 点击 Minimap 跳转
function onMinimapClick(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const clickX = e.clientX - rect.left
  const clickY = e.clientY - rect.top

  // 计算对应的画布坐标（统一使用 scale）
  const canvasX = clickX / scale
  const canvasY = clickY / scale

  // 计算偏移，使点击位置居中显示
  const targetOffsetX = -(canvasX - props.viewportWidth / 2)
  const targetOffsetY = -(canvasY - (props.viewportHeight - 64) / 2)

  emit('navigate', targetOffsetX, targetOffsetY)
}
</script>

<style scoped>
/* ---- 预览面板容器 ---- */
.preview-panel {
  position: absolute;
  top: 76px;
  left: 12px;
  z-index: 50;
  background: rgba(255, 250, 235, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(127, 99, 21, 0.15);
  pointer-events: auto;
  box-shadow:
    rgba(127, 99, 21, 0.1) 0px 4px 16px,
    rgba(127, 99, 21, 0.06) 0px 8px 32px;
  user-select: none;
}

/* ---- 顶部栏 ---- */
.preview-top {
  display: flex;
  align-items: center;
  gap: 0;
  height: 40px;
  padding: 0 10px;
  border-bottom: 1px solid rgba(127, 99, 21, 0.1);
}

/* ---- 面包屑 ---- */
.preview-breadcrumb {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  overflow: hidden;
}

.preview-breadcrumb__root {
  font-family: var(--font-family);
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 1.2px;
  color: rgba(31, 31, 31, 0.45);
  text-transform: uppercase;
  white-space: nowrap;
}

.preview-breadcrumb__sep {
  font-size: 12px;
  color: rgba(127, 99, 21, 0.35);
}

.preview-breadcrumb__current {
  font-family: var(--font-family);
  font-size: 12px;
  font-weight: 400;
  letter-spacing: 1px;
  color: var(--color-text-primary);
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- 导航按钮组 ---- */
.preview-nav {
  display: flex;
  align-items: center;
  gap: 3px;
}

/* ---- 通用按钮 ---- */
.preview-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-text-primary);
  padding: 0;
  transition: background 0.15s ease, color 0.15s ease;
}

.preview-btn--collapse {
  width: 30px;
  height: 30px;
  color: rgba(31, 31, 31, 0.6);
  flex-shrink: 0;
}

.preview-btn--collapse:hover {
  background: rgba(127, 99, 21, 0.08);
  color: var(--color-text-primary);
}

.preview-btn--nav {
  width: 26px;
  height: 28px;
  color: rgba(31, 31, 31, 0.5);
}

.preview-btn--nav:hover {
  background: var(--color-mistral-black);
  color: var(--color-white);
}

/* ---- 主体（可折叠） ---- */
.preview-body {
  padding: 10px 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ---- Minimap ---- */
.minimap {
  position: relative;
  overflow: hidden;
  cursor: crosshair;
  border: 1px solid rgba(127, 99, 21, 0.12);
  flex-shrink: 0;
}

/* 画布白色背景底 */
.minimap__canvas-bg {
  position: absolute;
  inset: 0;
  background: #fff;
}

/* 四象限分割线 */
.minimap__divider-v {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  background: rgba(127, 99, 21, 0.15);
  z-index: 2;
  pointer-events: none;
}

.minimap__divider-h {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: rgba(127, 99, 21, 0.15);
  z-index: 2;
  pointer-events: none;
}

/* 象限标签 */
.minimap__label {
  position: absolute;
  font-family: var(--font-family);
  font-size: 9px;
  font-weight: 400;
  letter-spacing: 0.7px;
  color: rgba(127, 99, 21, 0.4);
  text-transform: uppercase;
  z-index: 3;
  pointer-events: none;
  line-height: 1;
}

.minimap__label--tl { top: 4px; left: 5px; }
.minimap__label--tr { top: 4px; right: 5px; text-align: right; }
.minimap__label--bl { bottom: 4px; left: 5px; }
.minimap__label--br { bottom: 4px; right: 5px; text-align: right; }

/* 卡片方块 */
.minimap__card {
  position: absolute;
  z-index: 4;
  pointer-events: none;
  transform-origin: top left;
}

/* 视口指示框 */
.minimap__viewport {
  position: absolute;
  z-index: 5;
  border: 1.5px solid #fa520f;
  background: rgba(250, 82, 15, 0.07);
  pointer-events: none;
  box-shadow: 0 0 0 0.5px rgba(250, 82, 15, 0.2);
}

/* ---- 区域指示点 ---- */
.preview-sections {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 2px 0 2px;
}

.preview-section-dot {
  width: 7px;
  height: 7px;
  background: rgba(127, 99, 21, 0.2);
  border: none;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s ease, transform 0.15s ease;
  flex-shrink: 0;
}

.preview-section-dot:hover {
  background: rgba(127, 99, 21, 0.45);
}

.preview-section-dot--active {
  background: var(--color-brand-orange);
  transform: scale(1.3);
}
</style>
