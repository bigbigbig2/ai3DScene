import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiTargetLabel } from '../api/http'
import { pingHealth, pingReady } from '../api/health'

export const useConnectionStore = defineStore('connection', () => {
  const healthOk = ref(false)
  const readyOk = ref(false)
  const checking = ref(false)
  const latencyMs = ref<number | null>(null)
  const lastCheckedAt = ref<string | null>(null)
  const error = ref<string | null>(null)

  const overallState = computed(() => {
    if (checking.value) return 'checking'
    if (healthOk.value && readyOk.value) return 'online'
    if (healthOk.value && !readyOk.value) return 'not-ready'
    return 'offline'
  })

  async function check() {
    checking.value = true
    error.value = null
    const started = performance.now()
    try {
      await pingHealth()
      healthOk.value = true
      await pingReady()
      readyOk.value = true
    } catch (caught) {
      healthOk.value = false
      readyOk.value = false
      error.value = caught instanceof Error ? caught.message : String(caught)
    } finally {
      latencyMs.value = Math.round(performance.now() - started)
      lastCheckedAt.value = new Date().toLocaleString()
      checking.value = false
    }
  }

  return {
    apiTargetLabel,
    healthOk,
    readyOk,
    checking,
    latencyMs,
    lastCheckedAt,
    error,
    overallState,
    check,
  }
})
