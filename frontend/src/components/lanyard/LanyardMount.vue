<template>
  <div ref="hostRef" class="lanyard-mount" role="presentation" />
</template>

<script setup lang="ts">
import { createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Lanyard from './Lanyard.jsx'
import LoginCardFace from './LoginCardFace.jsx'

const props = withDefaults(
  defineProps<{
    position?: [number, number, number]
    gravity?: [number, number, number]
    fov?: number
    transparent?: boolean
    frontImage?: string | null
    backImage?: string | null
    imageFit?: 'cover' | 'contain'
    lanyardImage?: string | null
    lanyardWidth?: number
    /** Embed interactive login UI on the 3D badge face */
    withLogin?: boolean
    feishuEnabled?: boolean
    loading?: boolean
    feishuLoading?: boolean
    hint?: string
  }>(),
  {
    position: () => [0, 0, 20],
    gravity: () => [0, -40, 0],
    fov: 20,
    transparent: true,
    frontImage: null,
    backImage: null,
    imageFit: 'cover',
    lanyardImage: null,
    lanyardWidth: 1,
    withLogin: false,
    feishuEnabled: false,
    loading: false,
    feishuLoading: false,
    hint: '',
  },
)

const emit = defineEmits<{
  submit: [username: string, password: string]
  feishu: []
}>()

const hostRef = ref<HTMLElement | null>(null)
let root: Root | null = null

function renderIsland() {
  if (!root) return

  const cardContent = props.withLogin
    ? createElement(LoginCardFace, {
        feishuEnabled: props.feishuEnabled,
        loading: props.loading,
        feishuLoading: props.feishuLoading,
        hint: props.hint,
        onSubmit: (username: string, password: string) => emit('submit', username, password),
        onFeishuLogin: () => emit('feishu'),
      })
    : null

  root.render(
    createElement(Lanyard, {
      position: props.position,
      gravity: props.gravity,
      fov: props.fov,
      transparent: props.transparent,
      frontImage: props.frontImage,
      backImage: props.backImage,
      imageFit: props.imageFit,
      lanyardImage: props.lanyardImage,
      lanyardWidth: props.lanyardWidth,
      cardContent,
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
    props.position,
    props.gravity,
    props.fov,
    props.transparent,
    props.frontImage,
    props.backImage,
    props.imageFit,
    props.lanyardImage,
    props.lanyardWidth,
    props.withLogin,
    props.feishuEnabled,
    props.loading,
    props.feishuLoading,
    props.hint,
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
.lanyard-mount {
  width: 100%;
  height: 100%;
  min-height: inherit;
}
</style>
