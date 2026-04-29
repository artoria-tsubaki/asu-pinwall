<template>
  <div class="table-row-detail">
    <header class="table-row-detail__header">
      <h1 class="table-row-detail__title">DISCOGRAPHY</h1>
      <button
        type="button"
        class="table-row-detail__close"
        aria-label="关闭并返回首页"
        @click="goHome"
      >
        <span class="table-row-detail__close-icon" aria-hidden="true">×</span>
      </button>
    </header>

    <div class="table-row-detail__scroll">
      <div v-if="!row" class="table-row-detail__empty">
        未找到对应曲目，请返回首页重试。
      </div>

      <template v-else>
        <div class="table-row-detail__main">
          <div class="table-row-detail__cover-wrap">
            <div class="table-row-detail__cover-card">
              <img
                v-if="coverUrl && !coverLoadError"
                class="table-row-detail__cover-img"
                :src="coverUrl"
                :alt="songLine"
                @error="coverLoadError = true"
              />
              <div
                v-else
                class="table-row-detail__cover-placeholder"
                aria-hidden="true"
              />
            </div>
          </div>

          <h2 class="table-row-detail__song-line">{{ songLine }}</h2>
          <p class="table-row-detail__date-line">{{ row.date }}</p>

          <div
            class="table-row-detail__desc"
            :class="{ 'table-row-detail__desc--muted': !descriptionText }"
          >
            {{ descriptionText || '暂无与 KAMITSUBAKI 唱片库匹配的详细文案。' }}
          </div>

          <div v-if="playerUrl" class="table-row-detail__video">
            <div class="table-row-detail__video-inner">
              <iframe
                :src="playerUrl"
                class="table-row-detail__iframe"
                :title="`Bilibili 视频 ${bvid || ''}`"
                allowfullscreen
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                referrerpolicy="strict-origin-when-cross-origin"
              />
            </div>
          </div>

          <a
            v-if="offsiteListenUrl"
            class="table-row-detail__offsite"
            :href="offsiteListenUrl"
            target="_blank"
            rel="noopener noreferrer"
          >在站外收听</a>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import asuMusicData from '../../../data/asu_music_data.json'
import albemuthMusicData from '../../../data/albemuth_music_data.json'
import {
  findDiscographyEntry,
  extractBvidFromUrl,
  getBilibiliPlayerUrl
} from '../utils/discographyMatch.js'
import { getDiscographyCoverUrl } from '../utils/discographyCovers.js'

const route = useRoute()
const router = useRouter()
const coverLoadError = ref(false)

const tableKey = computed(() => {
  const t = route.query.table
  if (t === 'albemuth-bilibili') return 'albemuth-bilibili'
  return 'original-songs'
})

const rowIndex = computed(() => {
  const n = Number(route.params.rowIndex)
  return Number.isFinite(n) ? n : -1
})

const tableRows = computed(() => {
  if (tableKey.value === 'albemuth-bilibili') {
    return albemuthMusicData?.rows
  }
  return asuMusicData?.rows
})

const row = computed(() => {
  const rows = tableRows.value
  if (!Array.isArray(rows) || rowIndex.value < 0 || rowIndex.value >= rows.length) {
    return null
  }
  return rows[rowIndex.value]
})

const discEntry = computed(() => {
  if (!row.value) return null
  const entries =
    tableKey.value === 'albemuth-bilibili'
      ? (albemuthMusicData?.discography ?? [])
      : (asuMusicData?.discography ?? [])
  return findDiscographyEntry(row.value, entries)
})

watch(
  () => rowIndex.value,
  () => {
    coverLoadError.value = false
  }
)

const coverUrl = computed(() => {
  if (!row.value || !discEntry.value?.src) return null
  return getDiscographyCoverUrl(discEntry.value.src)
})

const songLine = computed(() => (row.value ? String(row.value.title) : ''))

const descriptionText = computed(() => {
  const d = discEntry.value?.Desc
  return typeof d === 'string' && d.trim() ? d.trim() : ''
})

const bvid = computed(() => {
  const url = row.value?.watch?.url
  return url ? extractBvidFromUrl(url) : null
})

const playerUrl = computed(() => (bvid.value ? getBilibiliPlayerUrl(bvid.value) : null))

const offsiteListenUrl = computed(() => {
  if (!row.value?.watch?.url) return null
  if (bvid.value) return null
  return row.value.watch.url
})

function goHome() {
  router.push({ name: 'Home' })
}
</script>

<style scoped>
.table-row-detail {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  background: var(--color-warm-ivory, #fffaeb);
  color: var(--color-text-primary, #1f1f1f);
}

.table-row-detail__header {
  position: relative;
  z-index: 2;
  flex-shrink: 0;
  min-height: 120px;
  padding: var(--space-8) var(--space-10) var(--space-9);
  padding-right: calc(44px + var(--space-10) * 2);
}

.table-row-detail__title {
  margin: 0;
  margin-top: var(--space-12);
  max-width: 12em;
  font-size: clamp(var(--fs-feature), 4vw, var(--fs-subheading));
  font-weight: 400;
  line-height: 0.95;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: var(--color-text-primary, #1f1f1f);
}

.table-row-detail__close {
  position: absolute;
  top: var(--space-8);
  right: var(--space-8);
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

.table-row-detail__close:hover {
  background: rgba(127, 99, 21, 0.2);
}

.table-row-detail__close-icon {
  font-size: 28px;
  line-height: 1;
  font-weight: 300;
}

.table-row-detail__scroll {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 var(--space-10) var(--space-15);
  padding-top: var(--space-10);
}

.table-row-detail__empty {
  max-width: 720px;
  margin: var(--space-12) auto 0;
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--color-text-secondary, hsl(0, 0%, 24%));
}

.table-row-detail__main {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-12);
  padding-bottom: var(--space-15);
}

.table-row-detail__cover-wrap {
  display: flex;
  justify-content: center;
  width: 100%;
  padding-top: var(--space-8);
}

.table-row-detail__cover-card {
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: min(100%, 420px);
  width: 100%;
  padding: var(--space-12) var(--space-12) var(--space-12);
  background: var(--color-white, #fff);
  box-shadow: var(--shadow-card);
  border-radius: var(--radius, 0);
}

.table-row-detail__cover-img {
  display: block;
  max-width: 100%;
  height: auto;
  vertical-align: top;
}

.table-row-detail__cover-placeholder {
  width: 100%;
  min-height: 220px;
  max-width: 340px;
  background: linear-gradient(
    160deg,
    var(--color-cream, #fff0c2) 0%,
    rgba(255, 250, 235, 0.9) 100%
  );
  border: 1px solid rgba(127, 99, 21, 0.12);
}

.table-row-detail__song-line {
  margin: 0;
  max-width: 40rem;
  width: 100%;
  text-align: center;
  font-size: var(--fs-subheading);
  font-weight: 400;
  line-height: 1.15;
  color: var(--color-text-primary, #1f1f1f);
}

.table-row-detail__date-line {
  margin: calc(var(--space-3) * -1) 0 0;
  text-align: center;
  font-size: var(--fs-caption);
  color: var(--color-text-secondary, hsl(0, 0%, 24%));
  line-height: 1.43;
}

.table-row-detail__desc {
  max-width: 40rem;
  width: 100%;
  font-size: var(--fs-body);
  font-weight: 400;
  line-height: 1.7;
  white-space: pre-wrap;
  color: var(--color-text-primary, #1f1f1f);
}

.table-row-detail__desc--muted {
  color: var(--color-text-secondary, hsl(0, 0%, 24%));
}

.table-row-detail__video {
  width: 100%;
  max-width: 720px;
  margin-top: var(--space-6);
}

.table-row-detail__video-inner {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%;
  height: 0;
  overflow: hidden;
  background: var(--color-mistral-black, #1f1f1f);
  border-radius: var(--radius, 0);
  box-shadow: var(--shadow-card);
}

.table-row-detail__iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 0;
}

.table-row-detail__offsite {
  display: inline-block;
  margin-top: var(--space-7);
  font-size: var(--fs-body);
  line-height: 1.5;
  color: var(--color-brand-orange, #fa520f);
  text-decoration: none;
  border-bottom: 1px solid rgba(255, 138, 0, 0.35);
  transition: border-color 0.15s ease;
}

.table-row-detail__offsite:hover {
  border-bottom-color: var(--color-brand-orange, #fa520f);
}

@media (min-width: 1024px) {
  .table-row-detail__main {
    gap: var(--space-14);
  }

  .table-row-detail__title {
    margin-top: var(--space-13);
  }
}
</style>
