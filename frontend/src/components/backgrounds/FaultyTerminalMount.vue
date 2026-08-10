<template>
  <div ref="hostRef" class="faulty-terminal-mount" role="presentation" />
</template>

<script setup lang="ts">
import { createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import FaultyTerminal from './FaultyTerminal.jsx'

const props = withDefaults(
  defineProps<{
    scale?: number
    gridMul?: [number, number]
    digitSize?: number
    timeScale?: number
    scanlineIntensity?: number
    glitchAmount?: number
    flickerAmount?: number
    noiseAmp?: number
    curvature?: number
    tint?: string
    mouseReact?: boolean
    mouseStrength?: number
    pageLoadAnimation?: boolean
    brightness?: number
  }>(),
  {
    scale: 1.5,
    gridMul: () => [2, 1],
    digitSize: 1.2,
    timeScale: 0.5,
    scanlineIntensity: 0.5,
    glitchAmount: 1,
    flickerAmount: 1,
    noiseAmp: 1,
    curvature: 0.1,
    tint: '#00ff9f',
    mouseReact: true,
    mouseStrength: 0.5,
    pageLoadAnimation: true,
    brightness: 0.65,
  },
)

const hostRef = ref<HTMLElement | null>(null)
let root: Root | null = null

function renderIsland() {
  if (!root) return
  root.render(
    createElement(FaultyTerminal, {
      scale: props.scale,
      gridMul: props.gridMul,
      digitSize: props.digitSize,
      timeScale: props.timeScale,
      scanlineIntensity: props.scanlineIntensity,
      glitchAmount: props.glitchAmount,
      flickerAmount: props.flickerAmount,
      noiseAmp: props.noiseAmp,
      curvature: props.curvature,
      tint: props.tint,
      mouseReact: props.mouseReact,
      mouseStrength: props.mouseStrength,
      pageLoadAnimation: props.pageLoadAnimation,
      brightness: props.brightness,
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
    props.scale,
    props.gridMul,
    props.digitSize,
    props.timeScale,
    props.scanlineIntensity,
    props.glitchAmount,
    props.flickerAmount,
    props.noiseAmp,
    props.curvature,
    props.tint,
    props.mouseReact,
    props.mouseStrength,
    props.pageLoadAnimation,
    props.brightness,
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
.faulty-terminal-mount {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
</style>
