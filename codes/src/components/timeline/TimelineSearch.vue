<template>
  <div class="tl-search">
    <button
      type="button"
      class="tl-search__trigger"
      aria-label="打开活动时间线搜索"
      @click="open"
    >
      <svg
        class="tl-search__icon"
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        stroke-width="1.6"
        aria-hidden="true"
      >
        <circle cx="10.5" cy="10.5" r="5.5" />
        <path d="M14.5 14.5L20 20" stroke-linecap="round" />
      </svg>
      <span class="tl-search__trigger-label" aria-hidden="true">SEARCH</span>
    </button>

    <div
      v-show="isOpen"
      class="tl-search__backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="搜索活动时间线"
      @click.self="close"
    >
      <div class="tl-search__panel" @click.stop>
        <div class="tl-search__head">
          <input
            ref="inputRef"
            v-model="query"
            class="tl-search__input"
            type="search"
            placeholder="搜索投稿标题或日期"
            autocomplete="off"
            @keydown.esc="close"
          />
        </div>
        <ul class="tl-search__list" role="listbox">
          <li
            v-for="row in filtered"
            :key="row.key"
            class="tl-search__item"
            role="option"
            @click="select(row)"
          >
            <span class="tl-search__item-title">{{ row.headline }}</span>
            <span class="tl-search__item-date">{{ row.dateLabel }}</span>
          </li>
        </ul>
        <p v-if="!filtered.length" class="tl-search__empty">无匹配结果</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import mittBus from '../../utils/mittBus'

const props = defineProps({
  /**
   * 预先生成的可检索元数据，与 data.json 的 events 顺序一致
   */
  rows: {
    type: Array,
    required: true
  }
})

const isOpen = ref(false)
const query = ref('')
const inputRef = ref(null)

const filtered = computed(() => {
  const q = (query.value || '').trim().toLowerCase()
  if (!q) {
    return props.rows
  }
  return props.rows.filter(
    (r) =>
      (r.matchTitle && r.matchTitle.includes(q)) ||
      (r.matchDate && r.matchDate.includes(q))
  )
})

function open() {
  isOpen.value = true
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  isOpen.value = false
  query.value = ''
}

function select(row) {
  close()
  mittBus.emit('goto', row.slideIndex)
}

watch(isOpen, (v) => {
  if (v) {
    nextTick(() => inputRef.value?.focus())
  }
})
</script>

<style scoped>
.tl-search__trigger {
  position: fixed;
  left: var(--space-8);
  top: var(--space-8);
  z-index: 24;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-5);
  height: 44px;
  border: none;
  border-radius: 0;
  font-family: var(--font-family);
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-mistral-black, #1f1f1f);
  background: var(--color-cream, #fff0c2);
  cursor: pointer;
  box-shadow: rgba(127, 99, 21, 0.14) 0 4px 16px, rgba(127, 99, 21, 0.08) 0 1px 4px;
  transition: background 0.15s ease;
}

.tl-search__trigger:hover {
  background: var(--color-sunshine-300, #ffd06a);
}

.tl-search__icon {
  flex-shrink: 0;
}

.tl-search__trigger-label {
  line-height: 1;
}

.tl-search__backdrop {
  position: fixed;
  inset: 0;
  z-index: 23;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 100px;
  background: rgba(0, 0, 0, 0.5);
  box-sizing: border-box;
}

.tl-search__panel {
  width: 100%;
  max-width: 550px;
  max-height: min(70vh, 600px);
  display: flex;
  flex-direction: column;
  margin: 0 var(--space-5);
  background: var(--color-white);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: var(--shadow-card);
}

.tl-search__head {
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-input-border);
}

.tl-search__input {
  width: 100%;
  box-sizing: border-box;
  padding: var(--space-4) var(--space-4);
  font-family: var(--font-family);
  font-size: 15px;
  color: var(--color-text-primary);
  background: var(--color-warm-ivory);
  border: 1px solid var(--color-input-border);
  border-radius: 0;
  outline: none;
}

.tl-search__input:focus {
  border-color: var(--color-sunshine-700);
}

/* type=search 内置清除按钮：悬停为手型（WebKit / Chromium） */
.tl-search__input::-webkit-search-cancel-button {
  cursor: pointer;
}

.tl-search__list {
  margin: 0;
  padding: 0;
  list-style: none;
  overflow: auto;
  flex: 1;
}

.tl-search__item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  font-family: var(--font-family);
  font-size: 14px;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  transition: background 0.12s ease;
}

.tl-search__item:hover,
.tl-search__item:focus-within {
  background: var(--color-cream);
}

.tl-search__item-title {
  flex: 1;
  min-width: 0;
  color: var(--color-text-primary);
  line-height: 1.4;
}

.tl-search__item-date {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  opacity: 0.85;
}

.tl-search__empty {
  margin: 0;
  padding: var(--space-6);
  text-align: center;
  font-size: 14px;
  color: var(--color-text-secondary);
}

@media (max-width: 600px) {
  .tl-search__trigger {
    left: var(--space-4);
    top: var(--space-4);
    padding: 0 var(--space-4);
    font-size: 12px;
  }

  .tl-search__backdrop {
    padding-top: 72px;
  }
}
</style>
