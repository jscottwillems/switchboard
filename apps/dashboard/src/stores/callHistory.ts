import { opsData } from '@/data/client'
import type { CallSummary } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCallHistoryStore = defineStore('callHistory', () => {
  const calls = ref<CallSummary[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    if (!loaded.value) loading.value = true
    try {
      calls.value = await opsData.fetchCallHistory()
      loaded.value = true
      error.value = null
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to load call history'
    } finally {
      loading.value = false
    }
  }

  return { calls, loading, loaded, error, load }
})
