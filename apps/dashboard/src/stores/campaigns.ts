import { opsData } from '@/data/client'
import type { CampaignSummary } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useCampaignListStore = defineStore('campaignList', () => {
  const campaigns = ref<CampaignSummary[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    if (!loaded.value) loading.value = true
    error.value = null
    try {
      campaigns.value = await opsData.fetchCampaigns()
      loaded.value = true
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to load campaigns'
    } finally {
      loading.value = false
    }
  }

  return { campaigns, loading, loaded, error, load }
})
