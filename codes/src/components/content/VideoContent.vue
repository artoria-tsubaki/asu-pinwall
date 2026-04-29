<template>
  <div class="video-content">
    <!-- iframe 嵌入（YouTube / Bilibili 等） -->
    <div v-if="content.embedUrl" class="video-content__embed-wrap">
      <iframe
        :src="content.embedUrl"
        :title="content.title || 'video'"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
        class="video-content__iframe"
      ></iframe>
    </div>

    <!-- 本地/直链 video 标签 -->
    <div v-else-if="content.src" class="video-content__native-wrap">
      <video
        :src="content.src"
        :poster="content.poster"
        controls
        preload="metadata"
        class="video-content__video"
      ></video>
    </div>

    <!-- 描述文字 -->
    <p v-if="content.description" class="video-content__desc">{{ content.description }}</p>

    <!-- 时长标签 -->
    <div v-if="content.duration" class="video-content__meta">
      <span class="video-content__badge">▶ {{ content.duration }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  content: {
    type: Object,
    default: () => ({})
  }
})
</script>

<style scoped>
.video-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* ---- iframe 响应式容器（16:9） ---- */
.video-content__embed-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: var(--color-mistral-black);
  overflow: hidden;
}

.video-content__iframe {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

/* ---- 原生 video ---- */
.video-content__native-wrap {
  width: 100%;
}

.video-content__video {
  display: block;
  width: 100%;
  height: auto;
  border-radius: var(--radius);
  background: var(--color-mistral-black);
}

/* ---- 描述 & 时长 ---- */
.video-content__desc {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.video-content__meta {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.video-content__badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px var(--space-5);
  background: var(--color-cream);
  font-size: 11px;
  letter-spacing: 0.5px;
  color: var(--color-mistral-black);
}
</style>
