import { livePollMs } from '@/data/apiConfig'
import { opsData } from '@/data/client'
import type { LiveCall } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLiveStore = defineStore('live', () => {
  const calls = ref<LiveCall[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  let inFlight = false
  let again = false
  let pollTimer: number | undefined

  async function load(): Promise<void> {
    if (inFlight) {
      again = true
      return
    }
    inFlight = true
    if (!loaded.value) loading.value = true
    try {
      calls.value = await opsData.fetchLiveCalls()
      loaded.value = true
      error.value = null
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to load live calls'
    } finally {
      loading.value = false
      inFlight = false
      if (again) {
        again = false
        void load()
      }
    }
  }

  function startPolling(): void {
    stopPolling()
    void load()
    pollTimer = window.setInterval(() => {
      void load()
    }, livePollMs())
  }

  function stopPolling(): void {
    if (pollTimer === undefined) return
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }

  return { calls, loading, loaded, error, load, startPolling, stopPolling }
})
