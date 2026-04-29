<template>
  <div class="mixed-content">
    <!--
      复合内容：content.blocks 为有序数组
      每个 block 有 type 字段，复用对应的单一内容组件
    -->
    <div
      v-for="(block, i) in content.blocks"
      :key="i"
      class="mixed-content__block"
      :class="`mixed-content__block--${block.type}`"
    >
      <TextContent   v-if="block.type === 'text'"   :content="block" />
      <ImageContent  v-else-if="block.type === 'image'"  :content="block" />
      <VideoContent  v-else-if="block.type === 'video'"  :content="block" />
      <TableContent  v-else-if="block.type === 'table'"  :content="block" />

      <!-- 分隔线 -->
      <div v-else-if="block.type === 'divider'" class="mixed-content__divider"></div>

      <!-- 行内强调 headline -->
      <p v-else-if="block.type === 'headline'" class="mixed-content__headline">
        {{ block.text }}
      </p>
    </div>
  </div>
</template>

<script setup>
import TextContent  from './TextContent.vue'
import ImageContent from './ImageContent.vue'
import VideoContent from './VideoContent.vue'
import TableContent from './TableContent.vue'

defineProps({
  content: {
    type: Object,
    default: () => ({ blocks: [] })
  }
})
</script>

<style scoped>
.mixed-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-7);
}

.mixed-content__block {
  /* 各块间通过 gap 控制间距，无需额外样式 */
}

.mixed-content__divider {
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(127, 99, 21, 0.2) 30%,
    rgba(127, 99, 21, 0.2) 70%,
    transparent
  );
}

.mixed-content__headline {
  font-size: var(--fs-subheading);
  font-weight: 400;
  color: var(--color-text-primary);
  line-height: 1.2;
  letter-spacing: -0.5px;
}
</style>
