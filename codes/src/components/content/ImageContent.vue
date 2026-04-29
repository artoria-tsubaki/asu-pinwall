<template>
  <div class="image-content">
    <!-- 单图 -->
    <figure v-if="!content.images" class="image-content__figure">
      <img
        :src="content.src"
        :alt="content.alt || ''"
        class="image-content__img"
        loading="lazy"
      />
      <figcaption v-if="content.caption" class="image-content__caption">
        {{ content.caption }}
      </figcaption>
    </figure>

    <!-- 图集（多图） -->
    <div v-else class="image-content__gallery" :class="`image-content__gallery--${galleryLayout}`">
      <figure
        v-for="(img, i) in content.images"
        :key="i"
        class="image-content__figure"
      >
        <img
          :src="img.src"
          :alt="img.alt || ''"
          class="image-content__img"
          loading="lazy"
        />
        <figcaption v-if="img.caption" class="image-content__caption">
          {{ img.caption }}
        </figcaption>
      </figure>
    </div>

    <!-- 图片说明文字 -->
    <p v-if="content.description" class="image-content__desc">{{ content.description }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  content: {
    type: Object,
    default: () => ({})
  }
})

const galleryLayout = computed(() => {
  const count = props.content.images?.length || 1
  if (count === 2) return 'two'
  if (count >= 3) return 'grid'
  return 'single'
})
</script>

<style scoped>
.image-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.image-content__figure {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.image-content__img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: var(--radius);
  object-fit: cover;
}

.image-content__caption {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
}

/* 两图并排 */
.image-content__gallery--two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
}

/* 三图以上 grid */
.image-content__gallery--grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-5);
}

.image-content__desc {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  line-height: 1.5;
}
</style>
