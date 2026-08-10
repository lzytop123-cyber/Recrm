<template>
  <div ref="hostRef" class="color-bends-mount" role="presentation" />
</template>

<script setup lang="ts">
import { createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import ColorBends from './ColorBends.jsx'

const props = withDefaults(
  defineProps<{
    colors?: string[]
    rotation?: number
    speed?: number
    transparent?: boolean
    autoRotate?: number
    scale?: number
    frequency?: number
    warpStrength?: number
    mouseInfluence?: number
    parallax?: number
    noise?: number
    iterations?: number
    intensity?: number
    bandWidth?: number
  }>(),
  {
    colors: () => ['#29ffdb', '#bc719d', '#7cff67', '#da0b0b'],
    rotation: 90,
    speed: 0.2,
    transparent: true,
    autoRotate: 0,
    scale: 1,
    frequency: 1,
    warpStrength: 1,
    mouseInfluence: 1,
    parallax: 0.5,
    noise: 0.15,
    iterations: 1,
    intensity: 1.5,
    bandWidth: 6,
  },
)

const hostRef = ref<HTMLElement | null>(null)
let root: Root | null = null

function renderIsland() {
  if (!root) return
  root.render(
    createElement(ColorBends, {
      colors: props.colors,
      rotation: props.rotation,
      speed: props.speed,
      transparent: props.transparent,
      autoRotate: props.autoRotate,
      scale: props.scale,
      frequency: props.frequency,
      warpStrength: props.warpStrength,
      mouseInfluence: props.mouseInfluence,
      parallax: props.parallax,
      noise: props.noise,
      iterations: props.iterations,
      intensity: props.intensity,
      bandWidth: props.bandWidth,
    }),
  )
}

onMounted(() => {
  if (!hostRef.value) return
  root = createRoot(hostRef.value)
  renderIsland()
})

watch(
  () => [
    props.colors,
    props.rotation,
    props.speed,
    props.transparent,
    props.autoRotate,
    props.scale,
    props.frequency,
    props.warpStrength,
    props.mouseInfluence,
    props.parallax,
    props.noise,
    props.iterations,
    props.intensity,
    props.bandWidth,
  ],
  () => renderIsland(),
  { deep: true },
)

onBeforeUnmount(() => {
  root?.unmount()
  root = null
})
</script>

<style scoped>
.color-bends-mount {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
</style>
