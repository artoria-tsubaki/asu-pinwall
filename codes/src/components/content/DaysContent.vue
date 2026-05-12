<template>
  <div class="days-content" role="status" :aria-label="ariaLabel">
    <div class="days-content__stage">
      <div class="days-content__stage-inner">
        <div class="days-content__stage-head">
          <p class="days-content__kicker-line">
            <span class="days-content__kicker-mark">CAREER</span>
            <span class="days-content__kicker-sep" aria-hidden="true">·</span>
            <span class="days-content__kicker-label">{{ content.label || '出道日' }}</span>
          </p>
          <p v-if="tagline" class="days-content__tagline">{{ tagline }}</p>
        </div>

        <!-- 切换按钮：始终绝对定位在右上角 -->
        <button
          type="button"
          class="days-content__toggle"
          @click="mode = mode === 'days' ? 'ymd' : 'days'"
        >
          {{ mode === 'days' ? 'Y·M·D' : 'DAYS' }}
        </button>

        <!--
          固定舞台：两个面板绝对定位叠放，切换仅改 opacity，
          容器尺寸永远不变，卡片高宽保持稳定。
        -->
        <div class="days-content__panel" :class="{ 'days-content__panel--off': mode !== 'days' }">
          <div class="days-content__big-num">{{ dayCount }}</div>
          <div class="days-content__big-lbl">DAYS</div>
        </div>

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
    </div>

    <p v-if="anniversaryCaption" class="days-content__anniv">
      {{ anniversaryCaption }}
    </p>

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

/** 是否逢出道日纪念日（按本地日历月日） */
function isDebutAnniversaryToday(isoDate) {
  if (!isoDate) return false
  const parts = isoDate.split('-')
  if (parts.length !== 3) return false
  const mo = parseInt(parts[1], 10)
  const day = parseInt(parts[2], 10)
  if (!Number.isFinite(mo) || !Number.isFinite(day)) return false
  const t = toLocalDate(new Date())
  return t.getMonth() === mo - 1 && t.getDate() === day
}

/** 已满周年数（出道日为起点，每满一个年同日 +1） */
function completedDebutAnniversaries(isoDate) {
  if (!isoDate) return 0
  const parts = isoDate.split('-')
  if (parts.length !== 3) return 0
  let cur = new Date(
    parseInt(parts[0], 10),
    parseInt(parts[1], 10) - 1,
    parseInt(parts[2], 10)
  )
  const end = toLocalDate(new Date())
  let n = 0
  for (;;) {
    const next = new Date(cur)
    next.setFullYear(next.getFullYear() + 1)
    if (next > end) break
    n++
    cur = next
  }
  return n
}

/**
 * 距离「下一个」出道纪念日（月日同 debutDate）的整天数；
 * 若今天就是纪念日则为 0；数据非法时返回 null。
 */
function daysUntilNextAnniversary(isoDate) {
  if (!isoDate) return null
  const parts = isoDate.split('-')
  if (parts.length !== 3) return null
  const mo = parseInt(parts[1], 10)
  const day = parseInt(parts[2], 10)
  if (!Number.isFinite(mo) || !Number.isFinite(day)) return null
  const today = toLocalDate(new Date())
  if (today.getMonth() === mo - 1 && today.getDate() === day) return 0
  const ty = today.getFullYear()
  let target = new Date(ty, mo - 1, day)
  if (target < today) target = new Date(ty + 1, mo - 1, day)
  return Math.floor((target - today) / (1000 * 60 * 60 * 24))
}

const dayCount = computed(() => countDaysFrom(props.content.debutDate))
const ymd = computed(() => diffCalendarYmd(props.content.debutDate))

const tagline = computed(() => {
  const s = props.content.tagline
  return typeof s === 'string' && s.trim() ? s.trim() : ''
})

const formattedDebut = computed(() => {
  const d = props.content.debutDate
  if (!d) return '—'
  const parts = d.split('-')
  if (parts.length !== 3) return d
  return `${parts[0]}.${parts[1]}.${parts[2]}`
})

const anniversaryCaption = computed(() => {
  const iso = props.content.debutDate
  if (!iso) return ''
  if (isDebutAnniversaryToday(iso)) {
    const n = completedDebutAnniversaries(iso)
    if (n <= 0) return '今日为出道日'
    return `今日为出道纪念日 · 已满 ${n} 周年`
  }
  const left = daysUntilNextAnniversary(iso)
  if (left == null || left < 0) return ''
  return `距离下一出道纪念日还有 ${left} 天`
})

const ariaLabel = computed(() => {
  const { y, m, d } = ymd.value
  const base = `出道第 ${dayCount.value} 天，即 ${y} 年 ${m} 月 ${d} 天，出道日 ${formattedDebut.value}`
  const extra = anniversaryCaption.value
  return extra ? `${base}。${extra}` : base
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
  overflow: hidden;
  background: linear-gradient(
    125deg,
    var(--color-cream) 0%,
    rgba(255, 250, 235, 0.92) 55%,
    var(--color-white) 100%
  );
  box-shadow: inset 0 1px 0 rgba(127, 99, 21, 0.08);
}

.days-content__stage::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--gradient-mistral-block);
  z-index: 1;
  pointer-events: none;
}

.days-content__stage-inner {
  position: relative;
  min-height: 248px;
  padding: var(--space-6) var(--space-6) var(--space-5) var(--space-7);
}

.days-content__stage-head {
  position: relative;
  z-index: 1;
  padding-right: 88px;
  margin-bottom: var(--space-3);
}

.days-content__kicker-line {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  font-family: var(--font-family);
  line-height: 1.2;
}

.days-content__kicker-mark {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--color-brand-orange);
}

.days-content__kicker-sep {
  font-size: 10px;
  color: rgba(127, 99, 21, 0.35);
  user-select: none;
}

.days-content__kicker-label {
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-sunshine-900);
}

.days-content__tagline {
  margin: var(--space-2) 0 0;
  font-family: var(--font-family);
  font-size: var(--fs-caption);
  font-weight: 400;
  line-height: 1.35;
  color: var(--color-text-secondary);
  max-width: 28em;
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
  left: 0;
  right: 0;
  bottom: 0;
  top: 104px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0 var(--space-6) var(--space-4);
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

/* ── 纪念日提示 ─────────────────────────── */
.days-content__anniv {
  margin: 0;
  padding: var(--space-4) var(--space-8) 0;
  font-family: var(--font-family);
  font-size: var(--fs-caption);
  font-weight: 400;
  line-height: 1.45;
  color: var(--color-text-primary);
  text-align: center;
  letter-spacing: -0.15px;
}

/* ── 底部副文 ───────────────────────────── */
.days-content__caption {
  margin: 0;
  padding: var(--space-5) var(--space-8) var(--space-2);
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
  margin-top: calc(var(--space-2));
  padding: 0 var(--space-8) var(--space-5);
  text-align: center;
}

.days-content__timeline-link {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-family);
  font-size: var(--fs-caption);
  font-weight: 500;
  line-height: 1.43;
  letter-spacing: 0.02em;
  color: var(--color-brand-orange);
  text-decoration: none;
  padding: var(--space-3) var(--space-5) var(--space-3) var(--space-6);
  background: linear-gradient(
    120deg,
    rgba(250, 82, 15, 0.1) 0%,
    rgba(255, 252, 245, 0.95) 58%,
    rgba(255, 250, 235, 0.88) 100%
  );
  border: 1px solid rgba(250, 82, 15, 0.28);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.65),
    0 1px 3px rgba(127, 99, 21, 0.06);
  transition:
    color 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.days-content__timeline-link::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--gradient-mistral-block);
  pointer-events: none;
}

.days-content__timeline-link:hover {
  color: var(--color-text-on-dark);
  background: var(--color-brand-orange);
  border-color: var(--color-brand-orange);
  box-shadow:
    0 4px 14px rgba(250, 82, 15, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.days-content__timeline-link:hover::before {
  opacity: 0;
}

.days-content__timeline-arrow {
  font-size: 0.9em;
  transition: transform 0.15s ease;
}

.days-content__timeline-link:hover .days-content__timeline-arrow {
  transform: translateX(3px);
}
</style>
