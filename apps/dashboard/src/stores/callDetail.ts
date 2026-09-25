import { opsData } from '@/data/client'
import type { CallDetail } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCallDetailStore = defineStore('callDetail', () => {
  const detail = ref<CallDetail | null>(null)
  const loading = ref(false)
  const notFound = ref(false)
  const error = ref<string | null>(null)
  const requestedId = ref<string | null>(null)

  async function load(callId: string): Promise<void> {
    requestedId.value = callId
    loading.value = true
    notFound.value = false
    error.value = null
    detail.value = null
    try {
      const result = await opsData.fetchCallDetail(callId)
      if (requestedId.value !== callId) return
      if (!result) {
        notFound.value = true
        return
      }
      detail.value = result
    } catch (caught) {
      if (requestedId.value !== callId) return
      error.value = caught instanceof Error ? caught.message : 'Failed to load call'
    } finally {
      if (requestedId.value === callId) loading.value = false
    }
  }

  return { detail, loading, notFound, error, requestedId, load }
})
