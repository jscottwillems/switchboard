import AppShell from '@/components/AppShell.vue'
import CallDetailView from '@/views/CallDetailView.vue'
import CallsView from '@/views/CallsView.vue'
import CampaignDetailView from '@/views/CampaignDetailView.vue'
import CampaignsView from '@/views/CampaignsView.vue'
import LiveView from '@/views/LiveView.vue'
import NotFoundView from '@/views/NotFoundView.vue'
import ReportDetailView from '@/views/ReportDetailView.vue'
import ReportsView from '@/views/ReportsView.vue'
import SystemView from '@/views/SystemView.vue'
import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', redirect: '/dashboard/live' },
        { path: 'dashboard', redirect: '/dashboard/live' },
        { path: 'dashboard/live', name: 'live', component: LiveView },
        { path: 'dashboard/calls', name: 'calls', component: CallsView },
        { path: 'dashboard/calls/:id', name: 'call-detail', component: CallDetailView },
        { path: 'dashboard/campaigns', name: 'campaigns', component: CampaignsView },
        { path: 'dashboard/campaigns/:id', name: 'campaign-detail', component: CampaignDetailView },
        { path: 'dashboard/reports', name: 'reports', component: ReportsView },
        { path: 'dashboard/reports/:reportId', name: 'report-detail', component: ReportDetailView },
        { path: 'dashboard/system', name: 'system', component: SystemView },
        { path: ':pathMatch(.*)*', name: 'not-found', component: NotFoundView },
      ],
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})
