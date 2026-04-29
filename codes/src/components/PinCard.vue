<template>
  <SocialGrid
    v-if="card.type === 'social-grid'"
    :content="card.content"
  />
  <div v-else class="pin-card-wrapper">
    <!-- 图钉 -->
    <div
      class="pin"
      :style="{
        background: pinColor,
        boxShadow: `var(--shadow-pin)`
      }"
    >
      <div class="pin__shine"></div>
    </div>
    <!-- 细线（图钉到卡片的连接感） -->
    <div class="pin__stem"></div>

    <!-- 卡片主体 -->
    <div
      class="pin-card"
      :class="{
        'pin-card--wide': card.type === 'table',
        'pin-card--fixed': card.type === 'tweets',
        'pin-card--image-teaser': card.type === 'image-wall-teaser'
      }"
    >
      <!-- 卡片顶部色条（Mistral 渐变） -->
      <div class="pin-card__accent-bar"></div>

      <!-- 卡片标题区 -->
      <div v-if="card.title" class="pin-card__header">
        <span class="pin-card__type-badge">{{ typeLabelMap[card.type] || card.type }}</span>
        <h3 class="pin-card__title">{{ card.title }}</h3>
      </div>

      <!-- 内容区：按类型路由到对应组件 -->
      <div class="pin-card__body">
        <TextContent    v-if="card.type === 'text'"    :content="card.content" />
        <ImageContent   v-else-if="card.type === 'image'"   :content="card.content" />
        <VideoContent   v-else-if="card.type === 'video'"   :content="card.content" />
        <TableContent
          v-else-if="card.type === 'table'"
          :content="card.content"
          :row-detail-route-name="card.rowDetailRouteName"
          :row-detail-query="card.rowDetailQuery"
        />
        <MixedContent   v-else-if="card.type === 'mixed'"   :content="card.content" />
        <ProfileContent v-else-if="card.type === 'profile'" :content="card.content" />
        <DaysContent    v-else-if="card.type === 'days'"    :content="card.content" />
        <TweetsCarouselContent v-else-if="card.type === 'tweets'" :content="card.content" />
        <ImageWallRotatingContent v-else-if="card.type === 'image-wall-teaser'" :content="card.content" />
      </div>

      <!-- 卡片底部元数据 -->
      <div v-if="card.meta" class="pin-card__footer">
        <span class="pin-card__meta">{{ card.meta }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import TextContent    from './content/TextContent.vue'
import ImageContent   from './content/ImageContent.vue'
import VideoContent   from './content/VideoContent.vue'
import TableContent   from './content/TableContent.vue'
import MixedContent   from './content/MixedContent.vue'
import ProfileContent from './content/ProfileContent.vue'
import DaysContent    from './content/DaysContent.vue'
import TweetsCarouselContent from './content/TweetsCarouselContent.vue'
import ImageWallRotatingContent from './content/ImageWallRotatingContent.vue'
import SocialGrid from './SocialGrid.vue'

const props = defineProps({
  card: {
    type: Object,
    required: true
  }
})

const typeLabelMap = {
  text:    'TEXT',
  image:   'IMAGE',
  video:   'VIDEO',
  table:   'TABLE',
  mixed:   'MIXED',
  profile: 'PROFILE',
  'social-grid': 'SOCIAL',
  days: 'DAYS',
  tweets: 'X / NEWS',
  'image-wall-teaser': 'GALLERY'
}

const pinColor = computed(() => {
  return props.card.pin?.color || 'var(--color-brand-orange)'
})
</script>

<style scoped>
.pin-card-wrapper {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  /* 让 transform 从图钉中心点开始 */
  transform-origin: top center;
}

/* ---- 图钉头 ---- */
.pin {
  position: relative;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  z-index: 2;
  flex-shrink: 0;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.pin:hover {
  transform: scale(1.15);
}

/* 图钉高光 */
.pin__shine {
  position: absolute;
  top: 3px;
  left: 4px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.6);
}

/* 图钉到卡片的细杆 */
.pin__stem {
  width: 2px;
  height: 10px;
  background: linear-gradient(to bottom, rgba(127,99,21,0.5), rgba(127,99,21,0.15));
  flex-shrink: 0;
}

/* ---- 卡片 ---- */
.pin-card {
  background: var(--color-white);
  border-radius: var(--radius);
  box-shadow: var(--shadow-card);
  min-width: 240px;
  max-width: 480px;
  overflow: hidden;
  position: relative;
}

.pin-card--wide {
  max-width: 720px;
}

/* 与 cards.json 中 latest-tweets-asu 的 layout.w 一致，轮播切换时不改变整卡宽度 */
.pin-card--fixed {
  width: 440px;
  min-width: 440px;
  max-width: 440px;
}

.pin-card--image-teaser {
  width: 420px;
  min-width: 420px;
  max-width: 420px;
}

/* 顶部 Mistral 色条 */
.pin-card__accent-bar {
  height: 4px;
  background: var(--gradient-mistral-block);
}

/* ---- 标题区 ---- */
.pin-card__header {
  padding: var(--space-8) var(--space-8) var(--space-5);
  border-bottom: 1px solid rgba(127, 99, 21, 0.08);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.pin-card__type-badge {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 1.5px;
  color: var(--color-brand-orange);
  text-transform: uppercase;
}

.pin-card__title {
  font-size: var(--fs-feature);
  font-weight: 400;
  color: var(--color-text-primary);
  line-height: 1.25;
  letter-spacing: -0.3px;
}

/* ---- 内容区 ---- */
.pin-card__body {
  padding: var(--space-8);
}

/* ---- 底部元数据 ---- */
.pin-card__footer {
  padding: var(--space-5) var(--space-8);
  border-top: 1px solid rgba(127, 99, 21, 0.08);
}

.pin-card__meta {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
}
</style>
