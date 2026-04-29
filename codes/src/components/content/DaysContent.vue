<template>
  <div class="days-content" role="status" :aria-label="ariaLabel">
    <!--
      固定舞台：两个面板绝对定位叠放，切换仅改 opacity，
      容器尺寸永远不变，卡片高宽保持稳定。
    -->
    <div class="days-content__stage">
      <!-- 切换按钮：始终绝对定位在右上角 -->
      <button
        type="button"
        class="days-content__toggle"
        @click="mode = mode === 'days' ? 'ymd' : 'days'"
      >
        {{ mode === 'days' ? 'Y·M·D' : 'DAYS' }}
      </button>

      <!-- 面板 A：总天数 -->
      <div class="days-content__panel" :class="{ 'days-content__panel--off': mode !== 'days' }">
        <div class="days-content__big-num">{{ dayCount }}</div>
        <div class="days-content__big-lbl">DAYS</div>
      </div>

      <!-- 面板 B：年 · 月 · 天 -->
      <div class="days-content__panel" :class="{ 'days-content__panel--off': mode !== 'ymd' }">
        <div class="days-content__ymd">
          <div class="days-content__seg">
            <span class="days-content__seg-num">{{ ymd.y }}</span>
            <span class="days-content__seg-unit">年</span>
          </div>
          <div class="days-content__sep"></div>
          <div class="days-content__seg">
            <span class="days-content__seg-num">{{ ymd.m }}</span>
            <span class="days-content__seg-unit">月</span>
          </div>
          <div class="days-content__sep"></div>
          <div class="days-content__seg">
            <span class="days-content__seg-num">{{ ymd.d }}</span>
            <span class="days-content__seg-unit">天</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部出道日副文，始终显示 -->
    <p class="days-content__caption">自 {{ formattedDebut }} 出道</p>
    <p class="days-content__action">
      <router-link
        class="days-content__timeline-link"
        to="/timeline?from=debut"
        aria-label="进入明透活动时间线"
      >
        活动时间线
        <span class="days-content__timeline-arrow" aria-hidden="true">→</span>
      </router-link>
    </p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  content: {
    type: Object,
    default: () => ({})
  }
})

const mode = ref('days')

function toLocalDate(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function countDaysFrom(isoDate) {
  if (!isoDate) return 0
  const parts = isoDate.split('-')
  if (parts.length !== 3) return 0
  const start = new Date(
    parseInt(parts[0], 10),
    parseInt(parts[1], 10) - 1,
    parseInt(parts[2], 10)
  )
  const diff = (toLocalDate(new Date()) - toLocalDate(start)) / (1000 * 60 * 60 * 24)
  return diff >= 0 ? Math.floor(diff) : 0
}

function diffCalendarYmd(isoDate) {
  if (!isoDate) return { y: 0, m: 0, d: 0 }
  const parts = isoDate.split('-')
  if (parts.length !== 3) return { y: 0, m: 0, d: 0 }
  let cur = new Date(
    parseInt(parts[0], 10),
    parseInt(parts[1], 10) - 1,
    parseInt(parts[2], 10)
  )
  const end = toLocalDate(new Date())
  if (cur > end) return { y: 0, m: 0, d: 0 }

  let y = 0
  for (;;) {
    const next = new Date(cur)
    next.setFullYear(next.getFullYear() + 1)
    if (next > end) break
    y++
    cur = next
  }
  let m = 0
  for (;;) {
    const next = new Date(cur)
    next.setMonth(next.getMonth() + 1)
    if (next > end) break
    m++
    cur = next
  }
  const cur2 = new Date(cur)
  let d = 0
  while (cur2 < end) {
    cur2.setDate(cur2.getDate() + 1)
    d++
  }
  return { y, m, d }
}

const dayCount = computed(() => countDaysFrom(props.content.debutDate))
const ymd = computed(() => diffCalendarYmd(props.content.debutDate))

const formattedDebut = computed(() => {
  const d = props.content.debutDate
  if (!d) return '—'
  const parts = d.split('-')
  if (parts.length !== 3) return d
  return `${parts[0]}.${parts[1]}.${parts[2]}`
})

const ariaLabel = computed(() => {
  const { y, m, d } = ymd.value
  return `出道第 ${dayCount.value} 天，即 ${y} 年 ${m} 月 ${d} 天，出道日 ${formattedDebut.value}`
})
</script>

<style scoped>
/* ── 根容器 ────────────────────────────── */
.days-content {
  display: flex;
  flex-direction: column;
  /* 向外撑破 body 的 padding，让 stage 边缘贴卡片边 */
  margin: calc(-1 * var(--space-8));
  margin-bottom: 0;
}

/* ── 固定高度舞台 ────────────────────────── */
.days-content__stage {
  position: relative;
  height: 196px;            /* 固定高度，切换不会改变 */
  overflow: hidden;
  background: var(--color-cream);
}

/* ── 切换按钮 ───────────────────────────── */
.days-content__toggle {
  position: absolute;
  top: var(--space-5);
  right: var(--space-5);
  z-index: 2;
  font-family: var(--font-family);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: var(--color-text-on-dark);
  background: var(--color-mistral-black);
  border: none;
  padding: var(--space-3) var(--space-5);
  border-radius: 0;
  cursor: pointer;
  transition: background 0.15s ease;
  line-height: 1;
}

.days-content__toggle:hover {
  background: var(--color-brand-orange);
}

/* ── 面板基础 ───────────────────────────── */
.days-content__panel {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-6) var(--space-5);
  transition: opacity 0.25s ease;
}

.days-content__panel--off {
  opacity: 0;
  pointer-events: none;
}

/* ── 面板 A：总天数 ─────────────────────── */
.days-content__big-num {
  font-family: var(--font-family);
  font-size: 80px;
  font-weight: 400;
  line-height: 1;
  letter-spacing: -2.05px;
  color: var(--color-brand-orange);
  font-variant-numeric: tabular-nums;
}

.days-content__big-lbl {
  font-family: var(--font-family);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--color-sunshine-900);
}

/* ── 面板 B：年月日 ──────────────────────── */
.days-content__ymd {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0;
}

.days-content__seg {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-6);
}

.days-content__seg-num {
  font-family: var(--font-family);
  font-size: 52px;
  font-weight: 400;
  line-height: 1;
  letter-spacing: -1px;
  color: var(--color-brand-orange);
  font-variant-numeric: tabular-nums;
}

.days-content__seg-unit {
  font-family: var(--font-family);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--color-sunshine-900);
}

/* 段落间的竖分隔线 */
.days-content__sep {
  width: 1px;
  height: 52px;
  background: rgba(127, 99, 21, 0.25);
  flex-shrink: 0;
}

/* ── 底部副文 ───────────────────────────── */
.days-content__caption {
  margin: 0;
  padding: var(--space-5) var(--space-8);
  font-family: var(--font-family);
  font-size: var(--fs-caption);
  font-weight: 400;
  line-height: 1.43;
  color: var(--color-text-secondary);
  text-align: center;
}

/* ── 时间线入口（副文下方）────────────── */
.days-content__action {
  margin: 0;
  margin-top: calc(-1 * var(--space-2));
  padding: 0 var(--space-8) var(--space-5);
  text-align: center;
}

.days-content__timeline-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-family);
  font-size: var(--fs-caption);
  font-weight: 400;
  line-height: 1.43;
  color: var(--color-text-secondary);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: color 0.15s ease, border-color 0.15s ease;
}

.days-content__timeline-link:hover {
  color: var(--color-brand-orange);
  border-bottom-color: var(--color-brand-orange);
}

.days-content__timeline-arrow {
  font-size: 0.9em;
}
</style>
