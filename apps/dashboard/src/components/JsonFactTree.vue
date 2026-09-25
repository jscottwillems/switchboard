<script setup lang="ts">
import ProvenanceBadge from '@/components/ProvenanceBadge.vue'
import { factClassLabel, factClassRecordLayer, isFactClass } from '@/lib/reports'
import { computed } from 'vue'

const props = defineProps<{ value: unknown }>()

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const recordValue = computed(() => (isRecord(props.value) ? props.value : null))

const factClass = computed(() => {
  const source = recordValue.value
  if (!source) return null
  const raw = source.fact_class
  return typeof raw === 'string' && raw.length > 0 ? raw : null
})

const epistemic = computed(() => {
  const source = recordValue.value
  if (!source || typeof source.epistemic !== 'string') return null
  return source.epistemic
})

const mappedLayer = computed(() => {
  const current = factClass.value
  if (!current || !isFactClass(current)) return null
  return factClassRecordLayer(current)
})

const mappedLabel = computed(() => {
  const current = factClass.value
  if (!current || !isFactClass(current)) return null
  return factClassLabel(current)
})

const claimFields = computed(() => {
  const source = recordValue.value
  if (!source || !factClass.value) return []
  return Object.entries(source).filter(([key]) => key !== 'fact_class' && key !== 'epistemic')
})

const objectFields = computed(() => {
  const source = recordValue.value
  if (!source || factClass.value) return []
  return Object.entries(source)
})

function primitive(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}
</script>

<template>
  <span v-if="!recordValue && !Array.isArray(value)" class="json-primitive">{{ primitive(value) }}</span>
  <ol v-else-if="Array.isArray(value)" class="json-list">
    <li v-for="(item, index) in value" :key="index">
      <JsonFactTree :value="item" />
    </li>
  </ol>
  <article v-else-if="factClass" class="json-card" :data-prov="mappedLayer ?? undefined">
    <header class="intel-top">
      <ProvenanceBadge v-if="mappedLayer" :layer="mappedLayer" />
      <span v-else class="muted">Unmapped fact class</span>
      <span class="mono">{{ factClass }}</span>
      <span v-if="mappedLabel" class="muted">{{ mappedLabel }}</span>
      <span v-if="epistemic" class="muted">{{ epistemic }}</span>
    </header>
    <dl class="json-fields">
      <template v-for="[key, child] in claimFields" :key="key">
        <dt>{{ key }}</dt>
        <dd><JsonFactTree :value="child" /></dd>
      </template>
    </dl>
  </article>
  <dl v-else class="json-fields">
    <template v-for="[key, child] in objectFields" :key="key">
      <dt>{{ key }}</dt>
      <dd><JsonFactTree :value="child" /></dd>
    </template>
  </dl>
</template>
