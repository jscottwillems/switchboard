<script setup lang="ts">
import { callStateLabel, type CallSessionSummary } from "@switchboard/schemas";
import { onMounted } from "vue";

import { useCallsStore } from "./stores/calls";

const calls = useCallsStore();

onMounted(() => {
  void calls.load();
});

function label(call: CallSessionSummary): string {
  return callStateLabel(call.state);
}
</script>

<template>
  <main>
    <h1>Switchboard</h1>
    <p>Operator view of honeypot calls. This screen is a contract stub.</p>
    <p v-if="calls.error">{{ calls.error }}</p>
    <p v-else-if="calls.loaded && calls.items.length === 0">No calls yet.</p>
    <ul v-else>
      <li v-for="call in calls.items" :key="call.id">
        {{ call.caller_number_e164 }} → {{ call.called_number_e164 }} ({{ label(call) }})
      </li>
    </ul>
  </main>
</template>

<style>
body {
  font-family: sans-serif;
  margin: 2rem;
}
</style>
