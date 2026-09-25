import { opsData } from '@/data/client'
import type { CampaignDetail } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCampaignDetailStore = defineStore('campaignDetail', () => {
  const detail = ref<CampaignDetail | null>(null)
  const loading = ref(false)
  const notFound = ref(false)
  const error = ref<string | null>(null)
  const requestedId = ref<string | null>(null)

  async function load(campaignId: string): Promise<void> {
    requestedId.value = campaignId
    loading.value = true
    notFound.value = false
    error.value = null
    detail.value = null
    try {
      const result = await opsData.fetchCampaignDetail(campaignId)
      if (requestedId.value !== campaignId) return
      if (!result) {
        notFound.value = true
        return
      }
      detail.value = result
    } catch (caught) {
      if (requestedId.value !== campaignId) return
      error.value = caught instanceof Error ? caught.message : 'Failed to load campaign'
    } finally {
      if (requestedId.value === campaignId) loading.value = false
    }
  }

  return { detail, loading, notFound, error, requestedId, load }
})
