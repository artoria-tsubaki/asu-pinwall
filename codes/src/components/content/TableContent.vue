<template>
  <div class="table-content">
    <!-- 表格说明 -->
    <p v-if="content.description" class="table-content__desc">{{ content.description }}</p>

    <!-- 数据表格 -->
    <div
      class="table-content__scroll"
      @wheel.stop
    >
      <table class="table-content__table">
        <thead v-if="content.headers && content.headers.length">
          <tr>
            <th
              v-for="(header, i) in content.headers"
              :key="i"
              class="table-content__th"
            >{{ header }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, ri) in content.rows"
            :key="ri"
            class="table-content__tr"
            :class="{ 'table-content__tr--nav': rowDetailRouteName }"
            @click="onRowClick(ri)"
          >
            <td
              v-for="(cell, ci) in row"
              :key="ci"
              class="table-content__td"
              :class="{ 'table-content__td--highlight': isHighlight(cell) }"
            >
              <a
                v-if="isLinkCell(cell)"
                class="table-content__link"
                :href="cellHref(cell)"
                target="_blank"
                rel="noopener noreferrer"
                @click.stop
              >{{ cellLabel(cell) }}</a>
              <template v-else>{{ formatCell(cell) }}</template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 底部注释 -->
    <p v-if="content.note" class="table-content__note">{{ content.note }}</p>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  content: {
    type: Object,
    default: () => ({})
  },
  /** 传入路由 name 时，点击数据行跳转到该详情路由，params.rowIndex 为行下标 */
  rowDetailRouteName: {
    type: String,
    default: undefined
  },
  /** 与 rowDetailRouteName 一并传入的 query（如区分不同表格数据源） */
  rowDetailQuery: {
    type: Object,
    default: undefined
  }
})

const router = useRouter()

function onRowClick(rowIndex) {
  if (!props.rowDetailRouteName) return
  const loc = {
    name: props.rowDetailRouteName,
    params: { rowIndex: String(rowIndex) }
  }
  if (props.rowDetailQuery && Object.keys(props.rowDetailQuery).length) {
    loc.query = { ...props.rowDetailQuery }
  }
  router.push(loc)
}

function isHighlight(cell) {
  if (typeof cell === 'object' && cell !== null && !isLinkCell(cell)) {
    return cell.highlight === true
  }
  return false
}

function isLinkCell(cell) {
  return (
    typeof cell === 'object' &&
    cell !== null &&
    typeof cell.href === 'string' &&
    cell.href.length > 0
  )
}

function cellHref(cell) {
  return cell.href
}

function cellLabel(cell) {
  if (typeof cell.value === 'string' && cell.value) return cell.value
  return cell.href
}

function formatCell(cell) {
  if (typeof cell === 'object' && cell !== null) return cell.value ?? ''
  return cell
}
</script>

<style scoped>
.table-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.table-content__desc {
  font-size: var(--fs-body);
  color: var(--color-text-primary);
  line-height: 1.5;
}

/* ---- 表格视区：限高纵向滚动，不出现横向滚动条 ---- */
.table-content__scroll {
  max-height: 400px;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}

/* ---- 表格 ---- */
.table-content__table {
  width: 100%;
  table-layout: auto;
  border-collapse: collapse;
  font-size: var(--fs-body);
}

.table-content__th {
  padding: var(--space-5) var(--space-6);
  text-align: left;
  font-weight: 400;
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-brand-orange);
  background: var(--color-cream);
  border-bottom: 2px solid rgba(127, 99, 21, 0.2);
  white-space: normal;
  word-break: break-word;
  position: sticky;
  top: 0;
  z-index: 1;
}

.table-content__tr:nth-child(even) {
  background: rgba(255, 250, 235, 0.6);
}

.table-content__tr:hover {
  background: var(--color-cream);
}

.table-content__tr--nav {
  cursor: pointer;
}

.table-content__td {
  padding: var(--space-5) var(--space-6);
  color: var(--color-text-primary);
  border-bottom: 1px solid rgba(127, 99, 21, 0.08);
  line-height: 1.4;
  vertical-align: top;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.table-content__td--highlight {
  color: var(--color-brand-orange);
  font-weight: 400;
}

.table-content__link {
  color: var(--color-brand-orange);
  text-decoration: none;
  border-bottom: 1px solid rgba(255, 138, 0, 0.35);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.table-content__link:hover {
  border-bottom-color: var(--color-brand-orange);
}

.table-content__note {
  font-size: var(--fs-caption);
  color: var(--color-text-secondary);
  line-height: 1.5;
}
</style>
