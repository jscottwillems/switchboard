import { opsData } from '@/data/client'
import type { SystemHealth } from '@/types/models'
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSystemStore = defineStore('system', () => {
  const health = ref<SystemHealth | null>(null)
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)

  async function load(): Promise<void> {
    if (!loaded.value) loading.value = true
    error.value = null
    try {
      health.value = await opsData.fetchSystemHealth()
      loaded.value = true
    } catch (caught) {
      error.value = caught instanceof Error ? caught.message : 'Failed to load system health'
    } finally {
      loading.value = false
    }
  }

  return { health, loading, loaded, error, load }
})