<script setup lang="ts">
import ClassificationTag from '@/components/ClassificationTag.vue'
import DayBars from '@/components/DayBars.vue'
import IndicatorChips from '@/components/IndicatorChips.vue'
import LoadError from '@/components/LoadError.vue'
import PageHeader from '@/components/PageHeader.vue'
import { formatTimestamp } from '@/lib/format'
import { campaignStatusLabel } from '@/lib/labels'
import { useCampaignListStore } from '@/stores/campaigns'
import { onMounted } from 'vue'

const store = useCampaignListStore()

onMounted(() => {
  void store.load()
})
</script>

<template>
  <section class="page">
    <PageHeader
      kicker="Campaigns"
      title="Campaigns"
      description="Grouped scam waves with volume, shared indicators, and the calls you can open."
    />
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading campaigns…</p>
    <div v-else-if="store.loaded" class="campaign-grid" data-testid="campaign-list">
      <router-link
        v-for="campaign in store.campaigns"
        :key="campaign.id"
        class="camp-card"
        :to="`/dashboard/campaigns/${campaign.id}`"
      >
        <div class="camp-top">
          <span class="status-pill" :data-campaign="campaign.status">{{ campaignStatusLabel(campaign.status) }}</span>
          <DayBars :activity="campaign.activity" />
        </div>
        <h2>{{ campaign.name }}</h2>
        <ClassificationTag :classification="campaign.classification" />
        <p>{{ campaign.summary }}</p>
        <dl class="mini-stats">
          <div>
            <dt>Calls</dt>
            <dd>{{ campaign.callCount }}</dd>
          </div>
          <div>
            <dt>Active</dt>
            <dd>{{ campaign.activeCallCount }}</dd>
          </div>
          <div>
            <dt>Last seen</dt>
            <dd>{{ formatTimestamp(campaign.lastSeenAt) }}</dd>
          </div>
        </dl>
        <IndicatorChips :items="campaign.topIndicators" />
      </router-link>
      <p v-if="store.campaigns.length === 0" class="empty">No campaigns in this snapshot.</p>
    </div>
  </section>
</template>
