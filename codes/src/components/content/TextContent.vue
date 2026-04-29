<template>
  <div class="text-content">
    <!-- 标签列表 -->
    <div v-if="content.tags && content.tags.length" class="text-content__tags">
      <span
        v-for="tag in content.tags"
        :key="tag"
        class="text-content__tag"
      >{{ tag }}</span>
    </div>

    <!-- 主正文 -->
    <p
      v-if="content.text"
      class="text-content__body"
      :class="{ 'text-content__body--quote': content.style === 'quote' }"
    >{{ content.text }}</p>

    <!-- 引言样式 -->
    <blockquote
      v-if="content.style === 'quote' && content.author"
      class="text-content__author"
    >— {{ content.author }}</blockquote>

    <!-- 列表 -->
    <ul v-if="content.list && content.list.length" class="text-content__list">
      <li v-for="(item, i) in content.list" :key="i">{{ item }}</li>
    </ul>

    <!-- 高亮数字/指标 -->
    <div v-if="content.stat" class="text-content__stat">
      <span class="text-content__stat-value">{{ content.stat.value }}</span>
      <span class="text-content__stat-label">{{ content.stat.label }}</span>
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
.text-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* ---- 标签 ---- */
.text-content__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.text-content__tag {
  display: inline-block;
  padding: 2px var(--space-5);
  background: var(--color-cream);
  color: var(--color-mistral-black);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.8px;
  text-transform: uppercase;
}

/* ---- 正文 ---- */
.text-content__body {
  font-size: var(--fs-body);
  line-height: 1.6;
  color: var(--color-text-primary);
}

.text-content__body--quote {
  font-size: 18px;
  line-height: 1.5;
  color: var(--color-text-primary);
  border-left: 3px solid var(--color-brand-orange);
  padding-left: var(--space-6);
  margin-left: 0;
}

.text-content__author {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  font-style: normal;
}

/* ---- 列表 ---- */
.text-content__list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.text-content__list li {
  font-size: var(--fs-body);
  color: var(--color-text-primary);
  line-height: 1.5;
  padding-left: var(--space-6);
  position: relative;
}

.text-content__list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  width: 6px;
  height: 6px;
  background: var(--color-brand-orange);
}

/* ---- 指标数字 ---- */
.text-content__stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.text-content__stat-value {
  font-size: 40px;
  font-weight: 400;
  color: var(--color-brand-orange);
  letter-spacing: -1px;
  line-height: 1;
}

.text-content__stat-label {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
</style>
