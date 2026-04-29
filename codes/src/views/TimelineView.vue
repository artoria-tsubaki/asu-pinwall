<template>
  <div class="timeline-page">
    <button
      type="button"
      class="timeline-page__close"
      aria-label="关闭并返回首页"
      @click="goHome"
    >
      <span class="timeline-page__close-icon" aria-hidden="true">×</span>
    </button>
    <TimelineSearch :rows="searchRows" />
    <div
      id="timeline-embed"
      class="timeline-page__embed"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TimelineSearch from '../components/timeline/TimelineSearch.vue'
import rawTimeline from '../data/timeline.json'
import mittBus from '../utils/mittBus'

defineOptions({ name: 'TimelineView' })

const TL_LINK_ATTR = 'data-pinwall-tl-css'
const TL_SCRIPT_ATTR = 'data-pinwall-tl-js'

const route = useRoute()
const router = useRouter()

function goHome() {
  router.push({ name: 'Home' })
}

const searchRows = computed(() => {
  const list = rawTimeline.events || []
  return list.map((item, index) => {
    const sd = item.start_date
    const year = sd?.data?.year ?? sd?.year
    const month = sd?.data?.month ?? sd?.month
    const day = sd?.data?.day ?? sd?.day
    const dateLabel = [year, month, day].filter(Boolean).join('/')
    const headline = item.text?.headline || '—'
    return {
      key: `e-${index}`,
      headline,
      dateLabel,
      matchTitle: String(headline).toLowerCase(),
      matchDate: String(dateLabel).toLowerCase(),
      slideIndex: index + 1
    }
  })
})

const embedId = 'timeline-embed'
let timelineInstance = null
const isReady = ref(false)
let pendingGoto = null

function getAssetBase() {
  const b = import.meta.env.BASE_URL || '/'
  return b.endsWith('/') ? b : `${b}/`
}

function ensureTimelineCss() {
  if (document.querySelector(`link[${TL_LINK_ATTR}]`)) {
    return
  }
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = `${getAssetBase()}timelinejs/css/timeline.css`
  link.setAttribute(TL_LINK_ATTR, 'true')
  document.head.appendChild(link)
}

function loadTimelineScript() {
  if (window.TL) {
    return Promise.resolve()
  }
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[${TL_SCRIPT_ATTR}]`)) {
      const t = setInterval(() => {
        if (window.TL) {
          clearInterval(t)
          resolve()
        }
      }, 30)
      setTimeout(() => {
        clearInterval(t)
        if (window.TL) resolve()
        else reject(new Error('TimelineJS load timeout'))
      }, 15000)
      return
    }
    const script = document.createElement('script')
    script.src = `${getAssetBase()}timelinejs/js/timeline.js`
    script.setAttribute(TL_SCRIPT_ATTR, 'true')
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load timeline.js'))
    document.body.appendChild(script)
  })
}

function getTimelineLanguage() {
  if (typeof navigator === 'undefined') return 'zh-cn'
  return navigator.language && navigator.language.toLowerCase().startsWith('zh')
    ? 'zh-cn'
    : 'en'
}

function applyRouteGo() {
  const q = route.query?.go
  if (q === undefined || q === null || q === '') {
    return
  }
  const n = parseInt(String(q), 10)
  if (Number.isNaN(n) || n < 1) {
    return
  }
  runGoto(n)
}

function runGoto(index) {
  if (!isReady.value || !timelineInstance) {
    pendingGoto = index
    return
  }
  if (typeof timelineInstance.goTo === 'function') {
    timelineInstance.goTo(index)
  }
}

function onGotoFromSearch(index) {
  runGoto(index)
}

function onTimelineLoaded() {
  isReady.value = true
  if (pendingGoto != null) {
    const i = pendingGoto
    pendingGoto = null
    if (timelineInstance && typeof timelineInstance.goTo === 'function') {
      timelineInstance.goTo(i)
    }
    return
  }
  applyRouteGo()
}

onMounted(() => {
  isReady.value = false
  pendingGoto = null
  ensureTimelineCss()
  const embed = document.getElementById(embedId)
  if (embed) {
    embed.innerHTML = ''
  }

  mittBus.on('goto', onGotoFromSearch)

  loadTimelineScript()
    .then(() => {
      if (!window.TL || !window.TL.Timeline) {
        return
      }
      const el = document.getElementById(embedId)
      if (!el) {
        return
      }
      const data = { ...rawTimeline }
      const options = {
        language: getTimelineLanguage(),
        initial_zoom: 4
      }
      timelineInstance = new window.TL.Timeline(embedId, data, options)
      timelineInstance.on('loaded', onTimelineLoaded)
    })
    .catch(() => {
      isReady.value = false
    })
})

onBeforeUnmount(() => {
  mittBus.off('goto', onGotoFromSearch)
  timelineInstance = null
  isReady.value = false
  const embed = document.getElementById(embedId)
  if (embed) {
    embed.innerHTML = ''
  }
})

watch(
  () => [route.query.go, isReady.value],
  () => {
    if (isReady.value) {
      applyRouteGo()
    }
  }
)
</script>

<style scoped>
.timeline-page {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-warm-ivory);
}

.timeline-page__close {
  position: fixed;
  top: var(--space-8);
  right: var(--space-8);
  z-index: 11;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(127, 99, 21, 0.12);
  color: var(--color-text-primary, #2b2110);
  cursor: pointer;
  transition: background 0.15s ease;
}

.timeline-page__close:hover {
  background: rgba(127, 99, 21, 0.2);
}

.timeline-page__close-icon {
  font-size: 28px;
  line-height: 1;
  font-weight: 300;
}

/* position: fixed; inset: 0 给父容器提供确定的视口高度，flex: 1 才能可靠分配剩余空间 */
.timeline-page__embed {
  position: relative;
  flex: 1;
  width: 100%;
  min-height: 0;
}
</style>
