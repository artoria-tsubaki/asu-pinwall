<template>
  <div class="profile-content">
    <!-- 头像区 -->
    <div class="profile-content__avatar-wrap">
      <div class="profile-content__avatar-ring">
        <img
          :src="content.avatar"
          :alt="content.name"
          class="profile-content__avatar"
          loading="lazy"
        />
      </div>
    </div>

    <!-- 姓名 + 身份 -->
    <div class="profile-content__identity">
      <h2 class="profile-content__name">{{ content.name }}</h2>
      <span class="profile-content__badge">{{ content.identity }}</span>
    </div>

    <!-- 分隔线 -->
    <div class="profile-content__divider"></div>

    <!-- 描述 -->
    <p class="profile-content__desc">{{ content.description }}</p>

    <!-- 代表作 -->
    <div v-if="content.works && content.works.length" class="profile-content__works">
      <span class="profile-content__works-label">WORKS</span>
      <ul class="profile-content__works-list">
        <li
          v-for="(work, i) in content.works"
          :key="i"
          class="profile-content__works-item"
        >{{ work }}</li>
      </ul>
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
.profile-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
}

/* ---- 头像 ---- */
.profile-content__avatar-wrap {
  padding-top: var(--space-4);
}

.profile-content__avatar-ring {
  width: 96px;
  height: 96px;
  padding: 3px;
  background: var(--gradient-mistral-block);
  border-radius: 50%;
  box-shadow:
    0 4px 16px rgba(127, 99, 21, 0.22),
    0 12px 32px rgba(127, 99, 21, 0.14);
}

.profile-content__avatar {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  background: var(--color-warm-ivory);
}

/* ---- 姓名 + 身份 ---- */
.profile-content__identity {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.profile-content__name {
  font-size: var(--fs-subheading);
  font-weight: 400;
  color: var(--color-text-primary);
  line-height: 1.1;
  letter-spacing: -0.5px;
}

.profile-content__badge {
  display: inline-block;
  padding: 3px 10px;
  background: var(--color-cream);
  color: var(--color-brand-orange);
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 1.8px;
  text-transform: uppercase;
}

/* ---- 分隔线 ---- */
.profile-content__divider {
  width: 100%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(127, 99, 21, 0.2) 25%,
    rgba(250, 82, 15, 0.35) 50%,
    rgba(127, 99, 21, 0.2) 75%,
    transparent
  );
}

/* ---- 描述 ---- */
.profile-content__desc {
  font-size: var(--fs-body);
  line-height: 1.75;
  color: var(--color-text-primary);
  text-align: left;
  width: 100%;
  white-space: pre-line;
}

/* ---- 代表作 ---- */
.profile-content__works {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-6);
  background: var(--color-warm-ivory);
}

.profile-content__works-label {
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 2px;
  color: var(--color-brand-orange);
  text-transform: uppercase;
}

.profile-content__works-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.profile-content__works-item {
  font-size: var(--fs-body);
  color: var(--color-text-primary);
  line-height: 1.5;
  padding-left: var(--space-6);
  position: relative;
}

.profile-content__works-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  width: 6px;
  height: 6px;
  background: var(--gradient-mistral-block);
}
</style>
