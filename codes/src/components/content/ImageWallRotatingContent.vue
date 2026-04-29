<template>
  <div
    class="image-wall-rotating"
    role="button"
    tabindex="0"
    :aria-label="'图片集锦，点击进入瀑布流'"
    @click="openWall"
    @keydown.enter.prevent="openWall"
    @keydown.space.prevent="openWall"
  >
    <div class="image-wall-rotating__viewport">
      <Transition name="iw-slide-fade" mode="out-in">
        <img
          :key="activeIndex"
          :src="current.src"
          :alt="current.alt || ''"
          class="image-wall-rotating__img"
          loading="lazy"
          draggable="false"
        />
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { setImageWallPayload } from '../../utils/imageWallStorage.js'

const props = defineProps({
  content: {
    type: Object,
    default: () => ({ images: [] })
  }
})

const router = useRouter()
const activeIndex = ref(0)

const slides = computed(() => {
  const list = Array.isArray(props.content.images) ? props.content.images : []
  return list.filter((i) => i && i.src)
})

const current = computed(() => slides.value[activeIndex.value] || { src: '', alt: '' })

const intervalMs = computed(() => {
  const n = Number(props.content.intervalMs)
  return Number.isFinite(n) && n >= 1200 ? n : 4500
})

let timer = null

function tick() {
  const n = slides.value.length
  if (n <= 1) return
  activeIndex.value = (activeIndex.value + 1) % n
}

function startTimer() {
  stopTimer()
  if (slides.value.length <= 1) return
  timer = setInterval(tick, intervalMs.value)
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch([slides, intervalMs], () => {
  activeIndex.value = 0
  startTimer()
})

onMounted(() => {
  startTimer()
})

onUnmounted(() => {
  stopTimer()
})

function openWall() {
  if (!slides.value.length) return
  setImageWallPayload(slides.value.map((i) => ({ src: i.src, alt: i.alt || '' })))
  router.push({ name: 'ImageWall' })
}
</script>

<style scoped>
.image-wall-rotating {
  display: flex;
  flex-direction: column;
  cursor: pointer;
  outline: none;
  border-radius: var(--radius);
  margin: calc(var(--space-2) * -1);
  padding: var(--space-2);
  transition: background 0.15s ease;
}

.image-wall-rotating:hover,
.image-wall-rotating:focus-visible {
  background: rgba(127, 99, 21, 0.06);
}

.image-wall-rotating__viewport {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: var(--radius);
  overflow: hidden;
  background: rgba(127, 99, 21, 0.08);
}

.image-wall-rotating__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  vertical-align: top;
  user-select: none;
  pointer-events: none;
}

/* 切换效果（可后续改为其它过渡名或动画） */
.iw-slide-fade-enter-active,
.iw-slide-fade-leave-active {
  transition: opacity 0.45s ease;
}

.iw-slide-fade-enter-from,
.iw-slide-fade-leave-to {
  opacity: 0;
}
</style>
