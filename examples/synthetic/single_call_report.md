# Single-call evidence report syn-call-001

> SYNTHETIC FIXTURE. Values in this report are copied from labeled synthetic inputs.

Upstream input schema: clerk.provisional_upstream.v0
Package ID: syn-pkg-call-001
Report ID: syn-pkg-call-001__single_call
Synthetic: true

## Provenance legend

### reported_caller_metadata

- fact_class: reported_caller_metadata
- epistemic: raw_observation
- definition: Displayed signaling or caller-ID values copied from the call record.

### spoken_identifier

- fact_class: spoken_identifier
- epistemic: raw_observation
- definition: Identifier values copied from supplied transcript excerpts.

### raw_observation

- fact_class: raw_observation
- epistemic: raw_observation
- definition: Source material, or an observation supplied without confirmation.

### confirmed_observation

- fact_class: confirmed_observation
- epistemic: raw_observation
- definition: Observation supplied with confirmation. This tag stays on the observation.

### derived_interpretation

- fact_class: derived_interpretation
- epistemic: derived_interpretation
- definition: Interpretation supplied as derived.

### derived_association

- fact_class: derived_association
- epistemic: campaign_attribution
- definition: Campaign link or association reason supplied as attribution.

## Call identity

### syn-call-001

- call_id: syn-call-001
- session_id: syn-session-001

## Timestamp

### syn-call-001

- fact_class: raw_observation
- epistemic: raw_observation
- call_id: syn-call-001
- started_at: 2026-09-20T15:04:00Z
- ended_at: 2026-09-20T15:07:07Z

## Displayed caller metadata

### syn-call-001

- fact_class: reported_caller_metadata
- epistemic: raw_observation
- call_id: syn-call-001
- displayed_caller_number: +1-202-555-0143
- displayed_caller_name: CARD SERVICES
- displayed_callee_number: +1-555-0100

## Call duration

### syn-call-001

- fact_class: raw_observation
- epistemic: raw_observation
- call_id: syn-call-001
- duration_seconds: 187

## Transcript excerpts

### syn-ex-001

- fact_class: raw_observation
- epistemic: raw_observation
- call_id: syn-call-001
- speaker: caller
- started_at: 2026-09-20T15:04:12Z
- ended_at: None in source package.
- text: This is the Visa fraud department. I am agent Marcus.

### syn-ex-002

- fact_class: raw_observation
- epistemic: raw_observation
- call_id: syn-call-001
- speaker: caller
- started_at: 2026-09-20T15:05:40Z
- ended_at: None in source package.
- text: Call me back at 1-800-555-0199 if we are disconnected.

### syn-ex-003

- fact_class: raw_observation
- epistemic: raw_observation
- call_id: syn-call-001
- speaker: caller
- started_at: 2026-09-20T15:06:10Z
- ended_at: None in source package.
- text: I need you to install a remote access program so I can secure the account.

## Spoken identifiers

### syn-spk-001

- fact_class: spoken_identifier
- epistemic: raw_observation
- call_id: syn-call-001
- kind: organization
- value: Visa
- excerpt_id: syn-ex-001
- recorded_at: 2026-09-20T15:04:12Z
- confidence_level: high
- confidence_score: 0.86
- confidence_basis: Confidence supplied with synthetic record syn-spk-001.

### syn-spk-002

- fact_class: spoken_identifier
- epistemic: raw_observation
- call_id: syn-call-001
- kind: person_name
- value: Marcus
- excerpt_id: syn-ex-001
- recorded_at: 2026-09-20T15:04:12Z
- confidence_level: high
- confidence_score: 0.80
- confidence_basis: Confidence supplied with synthetic record syn-spk-002.

### syn-spk-003

- fact_class: spoken_identifier
- epistemic: raw_observation
- call_id: syn-call-001
- kind: callback_number
- value: 1-800-555-0199
- excerpt_id: syn-ex-002
- recorded_at: 2026-09-20T15:05:40Z
- confidence_level: high
- confidence_score: 0.92
- confidence_basis: Confidence supplied with synthetic record syn-spk-003.

## Structured observations

### syn-obs-001

- fact_class: confirmed_observation
- epistemic: raw_observation
- confirmed: true
- call_id: syn-call-001
- category: impersonation
- statement: This is the Visa fraud department.
- recorded_at: 2026-09-20T15:04:12Z
- confidence_level: high
- confidence_score: 0.90
- confidence_basis: Confidence supplied with synthetic record syn-obs-001.
- supporting_excerpt_ids: syn-ex-001
- supporting_artifact_ids: None in source package.

### syn-obs-002

- fact_class: raw_observation
- epistemic: raw_observation
- confirmed: false
- call_id: syn-call-001
- category: requested_action
- statement: I need you to install a remote access program so I can secure the account.
- recorded_at: 2026-09-20T15:06:10Z
- confidence_level: medium
- confidence_score: 0.55
- confidence_basis: Confidence supplied with synthetic record syn-obs-002.
- supporting_excerpt_ids: syn-ex-003
- supporting_artifact_ids: None in source package.

### syn-obs-003

- fact_class: derived_interpretation
- epistemic: derived_interpretation
- confirmed: false
- call_id: syn-call-001
- category: script_similarity
- statement: Fixture marks opening wording as similar to synthetic script code SYN-SCRIPT-7.
- recorded_at: 2026-09-20T15:04:12Z
- confidence_level: low
- confidence_score: 0.35
- confidence_basis: Confidence supplied with synthetic record syn-obs-003.
- supporting_excerpt_ids: syn-ex-001
- supporting_artifact_ids: None in source package.

### syn-obs-004

- fact_class: confirmed_observation
- epistemic: raw_observation
- confirmed: true
- call_id: syn-call-001
- category: signaling
- statement: SIP From: <sip:+14155550138@example.invalid>
- recorded_at: 2026-09-20T15:04:00Z
- confidence_level: high
- confidence_score: 0.95
- confidence_basis: Confidence supplied with synthetic record syn-obs-004.
- supporting_excerpt_ids: None in source package.
- supporting_artifact_ids: syn-art-001

## Campaign association

### syn-campaign-001

- fact_class: derived_association
- epistemic: campaign_attribution
- label: Synthetic card-issuer impersonation
- packaged_call_id: syn-call-001
- member_call_id: syn-call-001
- member_call_id: syn-call-002
- confidence_level: high
- confidence_score: 0.80
- confidence_basis: Confidence supplied with synthetic record syn-campaign-001.

## Association reasons

### syn-reason-001

- fact_class: derived_association
- epistemic: campaign_attribution
- code: shared_spoken_callback
- statement: Both calls include spoken callback number 1-800-555-0199.
- call_id: syn-call-001
- call_id: syn-call-002
- confidence_level: high
- confidence_score: 0.92
- confidence_basis: Confidence supplied with synthetic record syn-reason-001.

### syn-reason-002

- fact_class: derived_association
- epistemic: campaign_attribution
- code: shared_displayed_cnam
- statement: Both calls display caller name CARD SERVICES.
- call_id: syn-call-001
- call_id: syn-call-002
- confidence_level: medium
- confidence_score: 0.60
- confidence_basis: Confidence supplied with synthetic record syn-reason-002.

## Supporting timestamps

### syn-call-001:call.started_at:2026-09-20T15:04:00Z

- fact_class: raw_observation
- epistemic: raw_observation
- source_id: syn-call-001
- label: call.started_at
- at: 2026-09-20T15:04:00Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-call-001:call.ended_at:2026-09-20T15:07:07Z

- fact_class: raw_observation
- epistemic: raw_observation
- source_id: syn-call-001
- label: call.ended_at
- at: 2026-09-20T15:07:07Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-ex-001:excerpt.started_at:2026-09-20T15:04:12Z

- fact_class: raw_observation
- epistemic: raw_observation
- source_id: syn-ex-001
- label: excerpt.started_at
- at: 2026-09-20T15:04:12Z
- call_id: syn-call-001
- excerpt_id: syn-ex-001
- artifact_id: None in source package.

### syn-ex-002:excerpt.started_at:2026-09-20T15:05:40Z

- fact_class: raw_observation
- epistemic: raw_observation
- source_id: syn-ex-002
- label: excerpt.started_at
- at: 2026-09-20T15:05:40Z
- call_id: syn-call-001
- excerpt_id: syn-ex-002
- artifact_id: None in source package.

### syn-ex-003:excerpt.started_at:2026-09-20T15:06:10Z

- fact_class: raw_observation
- epistemic: raw_observation
- source_id: syn-ex-003
- label: excerpt.started_at
- at: 2026-09-20T15:06:10Z
- call_id: syn-call-001
- excerpt_id: syn-ex-003
- artifact_id: None in source package.

### syn-spk-001:spoken_identifier.recorded_at:2026-09-20T15:04:12Z

- fact_class: spoken_identifier
- epistemic: raw_observation
- source_id: syn-spk-001
- label: spoken_identifier.recorded_at
- at: 2026-09-20T15:04:12Z
- call_id: syn-call-001
- excerpt_id: syn-ex-001
- artifact_id: None in source package.

### syn-spk-002:spoken_identifier.recorded_at:2026-09-20T15:04:12Z

- fact_class: spoken_identifier
- epistemic: raw_observation
- source_id: syn-spk-002
- label: spoken_identifier.recorded_at
- at: 2026-09-20T15:04:12Z
- call_id: syn-call-001
- excerpt_id: syn-ex-001
- artifact_id: None in source package.

### syn-spk-003:spoken_identifier.recorded_at:2026-09-20T15:05:40Z

- fact_class: spoken_identifier
- epistemic: raw_observation
- source_id: syn-spk-003
- label: spoken_identifier.recorded_at
- at: 2026-09-20T15:05:40Z
- call_id: syn-call-001
- excerpt_id: syn-ex-002
- artifact_id: None in source package.

### syn-obs-001:observation.recorded_at:2026-09-20T15:04:12Z

- fact_class: confirmed_observation
- epistemic: raw_observation
- source_id: syn-obs-001
- label: observation.recorded_at
- at: 2026-09-20T15:04:12Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-obs-002:observation.recorded_at:2026-09-20T15:06:10Z

- fact_class: raw_observation
- epistemic: raw_observation
- source_id: syn-obs-002
- label: observation.recorded_at
- at: 2026-09-20T15:06:10Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-obs-003:observation.recorded_at:2026-09-20T15:04:12Z

- fact_class: derived_interpretation
- epistemic: derived_interpretation
- source_id: syn-obs-003
- label: observation.recorded_at
- at: 2026-09-20T15:04:12Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-obs-004:observation.recorded_at:2026-09-20T15:04:00Z

- fact_class: confirmed_observation
- epistemic: raw_observation
- source_id: syn-obs-004
- label: observation.recorded_at
- at: 2026-09-20T15:04:00Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-reason-001:excerpt.started_at:2026-09-20T15:05:40Z

- fact_class: derived_association
- epistemic: campaign_attribution
- source_id: syn-reason-001
- label: excerpt.started_at
- at: 2026-09-20T15:05:40Z
- call_id: syn-call-001
- excerpt_id: syn-ex-002
- artifact_id: None in source package.

### syn-reason-001:excerpt.started_at:2026-09-21T13:15:20Z

- fact_class: derived_association
- epistemic: campaign_attribution
- source_id: syn-reason-001
- label: excerpt.started_at
- at: 2026-09-21T13:15:20Z
- call_id: syn-call-002
- excerpt_id: syn-ex-004
- artifact_id: None in source package.

### syn-reason-002:call.started_at:2026-09-20T15:04:00Z

- fact_class: derived_association
- epistemic: campaign_attribution
- source_id: syn-reason-002
- label: call.started_at
- at: 2026-09-20T15:04:00Z
- call_id: syn-call-001
- excerpt_id: None in source package.
- artifact_id: None in source package.

### syn-reason-002:call.started_at:2026-09-21T13:15:00Z

- fact_class: derived_association
- epistemic: campaign_attribution
- source_id: syn-reason-002
- label: call.started_at
- at: 2026-09-21T13:15:00Z
- call_id: syn-call-002
- excerpt_id: None in source package.
- artifact_id: None in source package.

## Relevant artifacts

### syn-art-001

- fact_class: raw_observation
- epistemic: raw_observation
- call_id: syn-call-001
- kind: signaling_log
- label: Synthetic SIP signaling excerpt
- uri: synthetic://artifacts/syn-call-001/signaling.log
- media_type: text/plain
- sha256: 0278b0bb458f7e26be733563e29976d66c482825194f40cf289a7a3f4bbe031d
- inline_text:
    # synthetic signaling excerpt syn-call-001
    SIP From: <sip:+14155550138@example.invalid>
    Displayed caller number: +1-202-555-0143
    P-Asserted-Identity: absent

## Confidence levels

### syn-spk-001

- fact_class: spoken_identifier
- epistemic: raw_observation
- confidence_level: high
- confidence_score: 0.86
- confidence_basis: Confidence supplied with synthetic record syn-spk-001.

### syn-spk-002

- fact_class: spoken_identifier
- epistemic: raw_observation
- confidence_level: high
- confidence_score: 0.80
- confidence_basis: Confidence supplied with synthetic record syn-spk-002.

### syn-spk-003

- fact_class: spoken_identifier
- epistemic: raw_observation
- confidence_level: high
- confidence_score: 0.92
- confidence_basis: Confidence supplied with synthetic record syn-spk-003.

### syn-obs-001

- fact_class: confirmed_observation
- epistemic: raw_observation
- confidence_level: high
- confidence_score: 0.90
- confidence_basis: Confidence supplied with synthetic record syn-obs-001.

### syn-obs-002

- fact_class: raw_observation
- epistemic: raw_observation
- confidence_level: medium
- confidence_score: 0.55
- confidence_basis: Confidence supplied with synthetic record syn-obs-002.

### syn-obs-003

- fact_class: derived_interpretation
- epistemic: derived_interpretation
- confidence_level: low
- confidence_score: 0.35
- confidence_basis: Confidence supplied with synthetic record syn-obs-003.

### syn-obs-004

- fact_class: confirmed_observation
- epistemic: raw_observation
- confidence_level: high
- confidence_score: 0.95
- confidence_basis: Confidence supplied with synthetic record syn-obs-004.

### syn-campaign-001

- fact_class: derived_association
- epistemic: campaign_attribution
- confidence_level: high
- confidence_score: 0.80
- confidence_basis: Confidence supplied with synthetic record syn-campaign-001.

### syn-reason-001

- fact_class: derived_association
- epistemic: campaign_attribution
- confidence_level: high
- confidence_score: 0.92
- confidence_basis: Confidence supplied with synthetic record syn-reason-001.

### syn-reason-002

- fact_class: derived_association
- epistemic: campaign_attribution
- confidence_level: medium
- confidence_score: 0.60
- confidence_basis: Confidence supplied with synthetic record syn-reason-002.
