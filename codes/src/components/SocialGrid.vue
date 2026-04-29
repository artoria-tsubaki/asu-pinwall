<template>
  <div class="social-grid">
    <p v-if="content.sectionLabel" class="social-grid__kicker">
      {{ content.sectionLabel }}
    </p>
    <div class="social-grid__grid">
      <SocialIcon
        v-for="(item, i) in content.items"
        :key="i"
        :icon="item.icon || ''"
        :icon-src="item.iconSrc || ''"
        :icon-size="item.iconSize != null ? item.iconSize : (content.iconSize ?? 48)"
        :label="item.label"
        :url="item.url"
      />
    </div>
  </div>
</template>

<script setup>
import SocialIcon from './SocialIcon.vue'

defineProps({
  content: {
    type: Object,
    default: () => ({ items: [] })
  }
})
</script>

<style scoped>
.social-grid {
  display: inline-block;
  padding: 0;
}

.social-grid__kicker {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 2px;
  color: var(--color-brand-orange);
  text-transform: uppercase;
  margin: 0 0 var(--space-6);
}

/* 三列同一排；神椿在数据顺序中放最后则显示在最右 */
.social-grid__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-6) var(--space-8);
  align-items: start;
  justify-items: center;
  min-width: 0;
  width: 100%;
  max-width: 360px;
}
</style>
