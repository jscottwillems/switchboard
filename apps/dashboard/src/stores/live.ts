import { opsData } from '@/data/client'
import type { LiveCall } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useLiveStore = defineStore('live', () => {
  const calls = ref<LiveCall[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    if (!loaded.value) loading.value = true
    error.value = null
    try {
      calls.value = await opsData.fetchLiveCalls()
      loaded.value = true
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to load live calls'
    } finally {
      loading.value = false
    }
  }

  return { calls, loading, loaded, error, load }
})
