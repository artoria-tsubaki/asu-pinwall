<template>
  <a
    class="social-icon"
    :href="url"
    target="_blank"
    rel="noopener noreferrer"
    :aria-label="label"
    :style="rootStyle"
  >
    <span class="social-icon__glyph" aria-hidden="true">
      <img
        v-if="resolvedSrc"
        class="social-icon__img"
        :src="resolvedSrc"
        :alt="''"
        loading="lazy"
        decoding="async"
        draggable="false"
      />
    </span>
    <span class="social-icon__label">{{ label }}</span>
  </a>
</template>

<script setup>
import { computed } from 'vue'
import youtubeAsset from '../assets/icons/youtube.svg'
import bilibiliAsset from '../assets/icons/bilibili.svg'
import kamitsubakiAsset from '../assets/icons/kamitsubaki.webp'

const BUILTIN_ICONS = {
  youtube: youtubeAsset,
  bilibili: bilibiliAsset,
  kamitsubaki: kamitsubakiAsset
}

const props = defineProps({
  /** 内置图标名：youtube、bilibili、kamitsubaki；与 iconSrc 二选一或同时存在时以 iconSrc 为准 */
  icon: {
    type: String,
    default: ''
  },
  /** 自定义图标图片地址（可由 import 或外链传入） */
  iconSrc: {
    type: String,
    default: ''
  },
  /** 图标区域边长（px），宽高一致 */
  iconSize: {
    type: Number,
    default: 48
  },
  label: {
    type: String,
    required: true
  },
  url: {
    type: String,
    required: true
  }
})

const resolvedSrc = computed(() => {
  if (props.iconSrc) return props.iconSrc
  if (props.icon && BUILTIN_ICONS[props.icon]) return BUILTIN_ICONS[props.icon]
  return ''
})

const rootStyle = computed(() => ({
  '--social-icon-size': `${props.iconSize}px`
}))
</script>

<style scoped>
.social-icon {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  text-decoration: none;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.social-icon__glyph {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--social-icon-size, 48px);
  height: var(--social-icon-size, 48px);
  line-height: 0;
  flex-shrink: 0;
}

.social-icon__img {
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.social-icon__label {
  display: block;
  font-size: var(--fs-caption);
  font-weight: 400;
  line-height: 1.43;
  padding: 2px 8px;
  text-align: center;
  color: var(--color-text-primary);
  transition: background-color 0.15s ease;
}

.social-icon:hover .social-icon__label {
  background: var(--color-cream);
}
</style>
