<template>
  <div
    class="tweets-carousel"
    @wheel.stop
  >
    <p v-if="content.sectionLabel" class="tweets-carousel__kicker">
      {{ content.sectionLabel }}
    </p>

    <div class="tweets-carousel__viewport">
      <article
        v-for="(tweet, i) in slides"
        v-show="i === activeIndex"
        :key="i"
        class="tweets-carousel__card twitter-card"
      >
        <div class="twitter-card__row">
          <div class="twitter-card__avatar-wrap">
            <img
              v-if="content.avatar"
              :src="content.avatar"
              alt=""
              class="twitter-card__avatar"
            />
            <span v-else class="twitter-card__avatar-fallback" aria-hidden="true">A</span>
          </div>
          <div class="twitter-card__head">
            <div class="twitter-card__name-line">
              <span class="twitter-card__name">{{ content.displayName || '明透' }}</span>
            </div>
            <div class="twitter-card__meta">
              <span class="twitter-card__handle">@{{ content.handle || 'ASU_virtual' }}</span>
              <span class="twitter-card__sep">·</span>
              <time
                :datetime="isoDate(tweet)"
                class="twitter-card__time"
              >{{ formatDate(tweet) }}</time>
            </div>
          </div>
        </div>

        <div
          class="twitter-card__body"
          v-html="tweet.text?.text || ''"
        />
        <a
          class="twitter-card__link"
          :href="tweetUrl(tweet)"
          target="_blank"
          rel="noopener noreferrer"
        >在 X 上查看</a>
      </article>
    </div>

    <div
      v-if="slides.length > 1"
      class="tweets-carousel__dots"
      role="tablist"
      :aria-label="'推文 ' + (activeIndex + 1) + ' / ' + slides.length"
    >
      <button
        v-for="(_, d) in slides"
        :key="d"
        type="button"
        class="tweets-carousel__dot"
        :class="{ 'tweets-carousel__dot--active': d === activeIndex }"
        :aria-label="`第 ${d + 1} 条`"
        :aria-current="d === activeIndex ? 'true' : undefined"
        @click="activeIndex = d"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  content: {
    type: Object,
    default: () => ({ items: [] })
  }
})

const activeIndex = ref(0)

const slides = computed(() => {
  const list = Array.isArray(props.content.items) ? props.content.items : []
  return list.slice(0, 5)
})

watch(slides, () => {
  activeIndex.value = 0
}, { deep: true })

function tweetUrl(tweet) {
  const c = tweet?.media?.caption || ''
  const m = c.match(/href="([^"]+)"/)
  return m ? m[1] : 'https://x.com/ASU_virtual'
}

function formatDate(tweet) {
  const d = tweet?.start_date
  if (!d) return ''
  return `${d.year}/${d.month}/${d.day}`
}

function isoDate(tweet) {
  const d = tweet?.start_date
  if (!d) return ''
  const mo = String(d.month).padStart(2, '0')
  const day = String(d.day).padStart(2, '0')
  return `${d.year}-${mo}-${day}`
}

</script>

<style scoped>
.tweets-carousel {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.tweets-carousel__kicker {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 2px;
  color: var(--color-brand-orange);
  text-transform: uppercase;
  margin: 0 0 var(--space-6);
}

/* 单卡视口：Twitter 摘要卡 + 暖色阴影（设计系统） */
.tweets-carousel__viewport {
  position: relative;
  min-height: 150px;
  width: 100%;
  box-sizing: border-box;
}

.twitter-card {
  background: var(--color-white);
  border: 1px solid rgba(127, 99, 21, 0.12);
  box-shadow: var(--shadow-card);
  padding: var(--space-5) var(--space-6);
  border-radius: var(--radius);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.twitter-card__row {
  display: flex;
  gap: var(--space-5);
  align-items: flex-start;
  margin-bottom: var(--space-4);
}

.twitter-card__avatar-wrap {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-cream);
  border: 1px solid rgba(127, 99, 21, 0.1);
}

.twitter-card__avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.twitter-card__avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 18px;
  color: var(--color-text-secondary);
}

.twitter-card__head {
  min-width: 0;
  flex: 1;
}

.twitter-card__name-line {
  line-height: 1.2;
}

.twitter-card__name {
  font-size: var(--fs-body);
  font-weight: 400;
  color: var(--color-text-primary);
  letter-spacing: -0.2px;
}

.twitter-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  line-height: 1.3;
}

.twitter-card__sep {
  user-select: none;
}

/* 正文：与推特多段 p 行为一致，限制高度可滚动 */
.twitter-card__body {
  font-size: 15px;
  line-height: 1.5;
  color: var(--color-text-primary);
  max-height: 180px;
  overflow-y: auto;
  margin-bottom: var(--space-5);
  word-break: break-word;
}

.twitter-card__body :deep(p) {
  margin: 0 0 var(--space-3);
}

.twitter-card__body :deep(p:last-child) {
  margin-bottom: 0;
}

.twitter-card__link {
  display: inline-block;
  font-size: var(--fs-caption);
  font-weight: 400;
  color: var(--color-brand-orange);
  text-decoration: none;
  letter-spacing: 0.2px;
}

.twitter-card__link:hover {
  color: var(--color-sunshine-900);
  text-decoration: underline;
}

.tweets-carousel__dots {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  margin-top: var(--space-6);
  padding-top: var(--space-2);
}

/* 透明大按钮便于点按，圆点视觉上由 ::after 绘制（8px） */
.tweets-carousel__dot {
  position: relative;
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  flex-shrink: 0;
}

.tweets-carousel__dot::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 8px;
  height: 8px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: rgba(127, 99, 21, 0.2);
  transition: background 0.15s ease, transform 0.15s ease;
}

.tweets-carousel__dot:hover::after {
  background: rgba(127, 99, 21, 0.45);
}

.tweets-carousel__dot--active::after {
  background: var(--color-brand-orange);
  transform: translate(-50%, -50%) scale(1.25);
}
</style>
