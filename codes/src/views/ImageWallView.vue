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

    <main ref="scrollRootRef" class="image-wall-page__main">
      <div v-if="!images.length" class="image-wall-page__empty">
        暂无图片，请从图钉墙卡片进入。
      </div>
      <div v-else class="image-wall-page__masonry">
        <figure
          v-for="(img, i) in images"
          :key="i + img.src"
          class="image-wall-page__figure"
          :data-lazy-index="i"
        >
          <img
            v-if="loaded[i]"
            :src="img.src"
            :alt="img.alt || ''"
            class="image-wall-page__img"
            decoding="async"
          />
          <div
            v-else
            class="image-wall-page__placeholder"
            aria-hidden="true"
          />
        </figure>
      </div>
    </main>
  </div>
</template>

<script setup>
defineOptions({ name: 'ImageWallView' })

import { onMounted, onUnmounted, reactive, ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { getImageWallPayload } from '../utils/imageWallStorage.js'

const router = useRouter()
const images = ref([])
const scrollRootRef = ref(null)
/** 已通过 IntersectionObserver 决定加载的图片下标（进入视口或预取区后才置 true） */
const loaded = reactive({})

let lazyObserver = null

onMounted(async () => {
  images.value = getImageWallPayload()
  await nextTick()
  const root = scrollRootRef.value
  if (!root || !images.value.length) return

  lazyObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const raw = entry.target.getAttribute('data-lazy-index')
        const idx = raw == null ? NaN : Number(raw)
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

  root.querySelectorAll('[data-lazy-index]').forEach((el) => {
    lazyObserver.observe(el)
  })
})

onUnmounted(() => {
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
  z-index: 10;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(127, 99, 21, 0.12);
  color: var(--color-text-primary);
  cursor: pointer;
  transition: background 0.15s ease;
}

.image-wall-page__close:hover {
  background: rgba(127, 99, 21, 0.2);
}

.image-wall-page__close-icon {
  font-size: 28px;
  line-height: 1;
  font-weight: 300;
}

.image-wall-page__main {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: calc(44px + var(--space-10) + var(--space-8)) var(--space-10)
    var(--space-12);
}

.image-wall-page__empty {
  max-width: 480px;
  margin: var(--space-12) auto 0;
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--color-text-secondary);
  text-align: center;
}

.image-wall-page__masonry {
  max-width: 1400px;
  margin: 0 auto;
  column-count: 2;
  column-gap: var(--space-8);
}

@media (min-width: 768px) {
  .image-wall-page__masonry {
    column-count: 3;
    column-gap: var(--space-10);
  }
}

@media (min-width: 1200px) {
  .image-wall-page__masonry {
    column-count: 4;
  }
}

.image-wall-page__figure {
  margin: 0 0 var(--space-8);
  break-inside: avoid;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--color-white);
  box-shadow: var(--shadow-card);
}

.image-wall-page__img {
  display: block;
  width: 100%;
  height: auto;
  vertical-align: top;
}

.image-wall-page__placeholder {
  min-height: 140px;
  width: 100%;
  background: linear-gradient(
    90deg,
    rgba(127, 99, 21, 0.06) 25%,
    rgba(127, 99, 21, 0.12) 50%,
    rgba(127, 99, 21, 0.06) 75%
  );
  background-size: 200% 100%;
  animation: image-wall-placeholder-shimmer 1.2s ease-in-out infinite;
}

@keyframes image-wall-placeholder-shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}
</style>
