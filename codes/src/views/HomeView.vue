<template>
  <PinWall :cards="cards" />
</template>

<script setup>
defineOptions({ name: 'HomeView' })

import PinWall from '../components/PinWall.vue'
import cardsData from '../data/cards.json'
import illusMeta from '../assets/images/illus/illus.json'
import asuMusicData from '../../../data/asu_music_data.json'
import albemuthMusicData from '../../../data/albemuth_music_data.json'
import { ref } from 'vue'
import careerVideoSrc from '../assets/video/明透 Op.1 - 「はじめまして。」.mp4'
import asuHeadSrc from '../assets/images/head/Asuhead.webp'
import debutData from '../data/debut.json'
import tweetsAsuVirtual from '../../../data/tweets_ASU_virtual_20260427_155644.json'

const illusModules = import.meta.glob('../assets/images/illus/*.{jpg,jpeg,png,webp}', {
  eager: true,
  import: 'default'
})
const illusTitleByFile = new Map(
  Array.isArray(illusMeta.items) ? illusMeta.items.map((it) => [it.file, it.title]) : []
)
const officialIllustrationImages = Object.keys(illusModules)
  .sort()
  .map((path) => {
    const file = path.replace(/^.*\//, '')
    const title = illusTitleByFile.get(file) || ''
    return {
      src: illusModules[path],
      alt: title || '官方绘图',
      ...(title ? { title } : {})
    }
  })

function buildOriginalSongsTableContent(data) {
  return {
    description: data.note,
    headers: data.columns,
    rows: data.rows.map((r) => [
      r.date,
      r.title,
      r.watch ? { href: r.watch.url, value: r.watch.label } : '—'
    ]),
    note: `来源：${data.source}`
  }
}

/** 本地资源需经 Vite 处理 URL，在注入后再交给对应内容组件 */
const cards = ref([
  ...cardsData.map((card) => {
    if (card.id === 'career-video') {
      return {
        ...card,
        content: {
          ...card.content,
          src: careerVideoSrc
        }
      }
    }
    if (card.id === 'profile-asu') {
      return {
        ...card,
        content: {
          ...card.content,
          avatar: asuHeadSrc
        }
      }
    }
    if (card.id === 'debut-days') {
      return {
        ...card,
        content: debutData
      }
    }
    if (card.id === 'latest-tweets-asu') {
      return {
        ...card,
        content: {
          ...card.content,
          items: Array.isArray(tweetsAsuVirtual) ? tweetsAsuVirtual.slice(0, 5) : [],
          avatar: asuHeadSrc
        }
      }
    }
    if (card.id === 'image-wall-teaser') {
      return {
        ...card,
        content: {
          ...card.content,
          images:
            officialIllustrationImages.length > 0
              ? officialIllustrationImages
              : Array.isArray(card.content?.images)
                ? card.content.images
                : []
        }
      }
    }
    return card
  }),
  {
    id: 'original-songs-table',
    x: 2280,
    y: 180,
    rotate: -0.8,
    zIndex: 3,
    pin: { color: '#ffc14d' },
    type: 'table',
    title: '原创曲',
    layout: { w: 720, h: 620 },
    content: buildOriginalSongsTableContent(asuMusicData),
    meta: '萌娘百科 · 明透',
    rowDetailRouteName: 'TableRowDetail',
    rowDetailQuery: { table: 'original-songs' }
  },
  {
    id: 'albemuth-bilibili-table',
    x: 3060,
    y: 400,
    rotate: 0.6,
    zIndex: 3,
    pin: { color: '#e8b4d4' },
    type: 'table',
    title: 'Albemuth 投稿',
    layout: { w: 720, h: 620 },
    content: buildOriginalSongsTableContent(albemuthMusicData),
    meta: 'Bilibili · 合集 3337044',
    rowDetailRouteName: 'TableRowDetail',
    rowDetailQuery: { table: 'albemuth-bilibili' }
  }
])
</script>
