import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** 响应式监听 matchMedia，用于移动端布局切换 */
export function useMatchMedia(query: string): Ref<boolean> {
  const matches = ref(false)
  let mq: MediaQueryList | null = null

  function sync() {
    matches.value = !!mq?.matches
  }

  onMounted(() => {
    mq = window.matchMedia(query)
    sync()
    mq.addEventListener('change', sync)
  })

  onBeforeUnmount(() => {
    mq?.removeEventListener('change', sync)
  })

  return matches
}
