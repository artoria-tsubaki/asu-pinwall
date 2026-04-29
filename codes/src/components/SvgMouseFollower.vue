<template>
  <svg
    ref="svgRef"
    class="svg-mouse-follower"
    aria-hidden="true"
    :width="width"
    :height="height"
  />
</template>

<script setup>
/**
 * 鼠标轨迹跟随：基于 ste-vg/svg-follower 思路，
 * 多色 SVG 彩带 + 低概率几何粒子；不依赖 RxJS / GSAP。
 */
import { ref, onMounted, onUnmounted } from 'vue'

const NS = 'http://www.w3.org/2000/svg'
const width = ref(window.innerWidth)
const height = ref(window.innerHeight)
const svgRef = ref(null)

const COLORS = [
  'var(--color-brand-orange, #fa520f)',
  'var(--color-sunshine-500, #ffb83e)',
  'var(--color-bright-yellow, #ffd900)',
  'var(--color-sunshine-700, #ffa110)',
  'var(--color-white, #ffffff)'
]

let lastX = -1
let lastY = -1
let rafId = 0
let running = false
const followers = []

class Follower {
  constructor(stage, color) {
    this.removeDelay = 400
    this.stage = stage
    this.color = color
    this.points = []
    this.line = document.createElementNS(NS, 'path')
    this.line.style.fill = this.color
    this.stage.appendChild(this.line)
  }

  getDrift() {
    return (Math.random() - 0.5) * 3
  }

  add(position) {
    let direction = { x: 0, y: 0 }
    if (this.points[0]) {
      direction.x = (position.x - this.points[0].position.x) * 0.25
      direction.y = (position.y - this.points[0].position.y) * 0.25
    }
    const point = {
      position,
      time: Date.now(),
      drift: {
        x: this.getDrift() + direction.x / 2,
        y: this.getDrift() + direction.y / 2
      },
      age: 0,
      direction
    }

    const shapeChance = Math.random()
    const chance = 0.1
    if (shapeChance < chance) this.makeCircle(point)
    else if (shapeChance < chance * 2) this.makeSquare(point)
    else if (shapeChance < chance * 3) this.makeTriangle(point)

    this.points.unshift(point)
  }

  createLine(points) {
    const path = [points.length ? 'M' : '']

    if (points.length > 0) {
      let forward = true
      let i = 0

      while (i >= 0) {
        const point = points[i]
        const offsetX = point.direction.x * ((i - points.length) / points.length) * 0.6
        const offsetY = point.direction.y * ((i - points.length) / points.length) * 0.6
        const x = point.position.x + (forward ? offsetY : -offsetY)
        const y = point.position.y + (forward ? offsetX : -offsetX)
        point.age += 0.2
        path.push(String(x + point.drift.x * point.age))
        path.push(String(y + point.drift.y * point.age))

        i += forward ? 1 : -1
        if (i === points.length) {
          i--
          forward = false
        }
      }
    }
    return path.join(' ')
  }

  trimStep() {
    if (this.points.length > 0) {
      const last = this.points[this.points.length - 1]
      const now = Date.now()
      if (last.time < now - this.removeDelay) this.points.pop()
    }
    this.line.setAttribute('d', this.createLine(this.points))
  }

  makeCircle(point) {
    const r = (Math.abs(point.direction.x) + Math.abs(point.direction.y)) * 1
    const circle = document.createElementNS(NS, 'circle')
    circle.setAttribute('r', String(r))
    circle.style.fill = this.color
    circle.setAttribute('cx', '0')
    circle.setAttribute('cy', '0')
    this.moveShape(circle, point)
  }

  makeSquare(point) {
    const size = (Math.abs(point.direction.x) + Math.abs(point.direction.y)) * 1.5
    const square = document.createElementNS(NS, 'rect')
    square.setAttribute('width', String(size))
    square.setAttribute('height', String(size))
    square.style.fill = this.color
    this.moveShape(square, point)
  }

  makeTriangle(point) {
    const size = (Math.abs(point.direction.x) + Math.abs(point.direction.y)) * 1.5
    const triangle = document.createElementNS(NS, 'polygon')
    triangle.setAttribute('points', `0,0 ${size},${size / 2} 0,${size}`)
    triangle.style.fill = this.color
    this.moveShape(triangle, point)
  }

  moveShape(shape, point) {
    const px = point.position.x
    const py = point.position.y
    const driftX = px + point.direction.x * (Math.random() * 20) + point.drift.x * (Math.random() * 10)
    const driftY = py + point.direction.y * (Math.random() * 20) + point.drift.y * (Math.random() * 10)
    const duration = 500 + Math.random() * 500
    const g = document.createElementNS(NS, 'g')
    g.appendChild(shape)
    this.stage.appendChild(g)

    const endAngle = (Math.random() * 2 - 1) * 360
    const anim = g.animate(
      [
        { transform: `translate(${px}px, ${py}px) scale(1) rotate(0deg)`, opacity: 1 },
        { transform: `translate(${driftX}px, ${driftY}px) scale(0) rotate(${endAngle}deg)`, opacity: 0.2 }
      ],
      { duration, easing: 'cubic-bezier(0.2, 0.75, 0.2, 1)', fill: 'forwards' }
    )
    anim.onfinish = () => {
      try {
        g.remove()
      } catch {
        // ignore
      }
    }
  }
}

function tick() {
  if (!running) return
  for (const f of followers) f.trimStep()
  rafId = requestAnimationFrame(tick)
}

function onResize() {
  width.value = window.innerWidth
  height.value = window.innerHeight
}

function onPointerMove(e) {
  const isTouch = e.touches && e.touches.length
  const x = isTouch ? e.touches[0].clientX : e.clientX
  const y = isTouch ? e.touches[0].clientY : e.clientY
  if (x === lastX && y === lastY) return
  lastX = x
  lastY = y
  for (const f of followers) f.add({ x, y })
}

onMounted(() => {
  const stage = svgRef.value
  if (!stage) return

  COLORS.forEach((c) => followers.push(new Follower(stage, c)))

  window.addEventListener('resize', onResize)
  window.addEventListener('mousemove', onPointerMove)
  window.addEventListener('touchmove', onPointerMove, { passive: true })

  running = true
  rafId = requestAnimationFrame(tick)
})

onUnmounted(() => {
  running = false
  if (rafId) cancelAnimationFrame(rafId)
  window.removeEventListener('resize', onResize)
  window.removeEventListener('mousemove', onPointerMove)
  window.removeEventListener('touchmove', onPointerMove)
  followers.length = 0
})
</script>

<style scoped>
.svg-mouse-follower {
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
  overflow: visible;
}
</style>
