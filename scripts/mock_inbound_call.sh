#!/bin/sh
# Send one mock inbound-call webhook. Requires the API and dev bypass or the mock signature header.
set -eu
base="${SWITCHBOARD_API:-http://localhost:8000}"
curl -sS -X POST "$base/v1/telephony/voice/mock" \
  -H "content-type: application/json" \
  -H "x-switchboard-mock-signature: dev" \
  -d "{\"provider_call_id\":\"demo-1\",\"from_e164\":\"+15551212000\",\"to_e164\":\"+15550001001\",\"timestamp\":\"2026-09-25T20:00:00Z\"}"
echo
