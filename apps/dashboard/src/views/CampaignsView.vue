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
      description="Attribution clusters. Status is hypothesized, corroborated, or closed. Volume and the sparkline are not on Campaign."
    />
    <LoadError v-if="store.error" :message="store.error" @retry="store.load()" />
    <p v-if="store.loading && !store.loaded" class="empty">Loading campaigns…</p>
    <div v-else-if="store.loaded" class="campaign-grid" data-testid="campaign-list">
      <router-link
        v-for="item in store.campaigns"
        :key="item.campaign.id"
        class="camp-card"
        :to="`/dashboard/campaigns/${item.campaign.id}`"
      >
        <div class="camp-top">
          <span class="status-pill" :data-campaign="item.campaign.status">{{ campaignStatusLabel(item.campaign.status) }}</span>
          <DayBars :activity="item.gaps.activity" />
        </div>
        <h2>{{ item.campaign.label }}</h2>
        <ClassificationTag :classification="item.gaps.classification" />
        <p>{{ item.campaign.summary }}</p>
        <dl class="mini-stats">
          <div>
            <dt>Calls</dt>
            <dd>{{ item.gaps.call_count }}</dd>
          </div>
          <div>
            <dt>In progress</dt>
            <dd>{{ item.gaps.active_call_count }}</dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>{{ formatTimestamp(item.campaign.updated_at) }}</dd>
          </div>
        </dl>
        <IndicatorChips :items="item.gaps.shared_indicators" />
      </router-link>
      <p v-if="store.campaigns.length === 0" class="empty">No campaigns in this snapshot.</p>
    </div>
  </section>
</template>
