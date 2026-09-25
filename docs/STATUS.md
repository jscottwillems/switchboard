# STATUS

ATLAS owns the full status-doc structure. This file only carries Sherlock's handoff so Loki is not blocked on that document. Fold this section into ATLAS's status doc when it exists. Do not treat the headings below as the approved cross-team status schema.

## HANDOFF — Sherlock → Loki

Elicit in this order during a live call. The field column is the goal id for goals_completed and goals_remaining.

| Rank | Field | Why Loki should elicit it |
| --- | --- | --- |
| 1 | `pretext_category` | Ask why they are calling and store the coarse pretext class. |
| 2 | `claimed_company` | Who they want the target to believe is calling. |
| 3 | `loan_amounts` | The offered or approved principal they are pitching. |
| 3 | `rates` | The interest rate or APR attached to the offer. |
| 3 | `fees` | The amount they want paid and the advance-fee ask. |
| 4 | `callback_numbers` | Direct number to reach the operation if the line drops. |
| 4 | `spoken_numbers` | Any other phone number they mention. |
| 4 | `case_or_reference_ids` | Ticket, case, claim, or confirmation identifiers. |
| 4 | `spoken_cli_claim` | The number they say they are calling from, distinct from carrier CLI. |
| 5 | `claimed_agent` | The alias or persona name they are using. |
| 5 | `claimed_department` | The pretext desk inside that organization. |
| 6 | `domains` | Spoken or partial host when they will not give a full URL. |
| 6 | `urls` | Campaign site or payment page. |
| 6 | `email_addresses` | Mailbox for documents or later messages. |
| 7 | `payment_methods` | Cash-out rail, stored with the payment_method enum. |
| 7 | `remote_access_tools` | Remote-control software they want installed. |
| 8 | `requested_information` | The data they are trying to harvest. |
| 9 | `script_phrases` | Let the pitch play so campaign lines are recorded. |
| 9 | `urgency_language` | Time pressure that is not itself a legal or account threat. |
| 9 | `threat_or_consequence_language` | Arrest, account freeze, or lawsuit language. |
| 9 | `transfer_events` | A live handoff to another caller. |
| 9 | `spoofed_authority_claims` | The spoken claim that they represent an authority. |
| 9 | `opening_script_text` | Let the first caller turns play so the opening script is captured. |
| 9 | `ivr_prompts` | Note each menu prompt they play. |
| 9 | `ivr_menu_path` | Keep the spoken order of those menu prompts. |
| 9 | `transfer_destination_claimed` | Ask which desk or number they are transferring to. |
| 9 | `script_language` | Note the language of the script when it is clear. |
| 10 | `follow_up_promises` | A promise to call back, send a link, or follow up later. |
| 11 | `other` | Badge numbers and identifiers that are not case or reference ids. |

Rank 11 is the catch-all field, not one of the ten elicit priorities.

### Goal ids

Use the field strings above verbatim in `goals_completed` and `goals_remaining`. They are `ObservationKind` values. Do not invent parallel names.

`pretext_category` enum, stored on that observation and repeated in `normalized_value`: `tax`, `bank`, `warranty`, `debt`, `prize`, `tech_support`, `government`, `utility`, `other`. The free-text purpose is the observation `value` (the spoken purpose span), not a second goal id.

`payment_method` enum, only on `payment_methods`: `gift_card`, `wire`, `crypto`, `remote_access`, `bank_verify`, `other`.

### Ownership

Sherlock owns typed Observation and Inference. Each observation is grounded in a transcript span plus confidence. Campaign association is Watson-owned; see the Watson handoff below. Loki does not emit those records and does not set an extraction confidence.

Optional soft handoff only, unverified breadcrumbs Sherlock may later check against the transcript:

```json
"elicited_hints": [
  {"goal": "callback_numbers", "surface_text": "call this number", "turn_index": 3}
]
```

`goal` is an `ObservationKind` value. Hints are not observations. Asking for a literal number, URL, host, email, or dollar amount still matters: the deterministic extractor only records obvious surface forms. See `docs/INTELLIGENCE.md`.

## HANDOFF — Sherlock → Watson

Score `Observation` and `Inference` records. Do not score call-layer metadata from this package. Timing windows, simultaneous calls, duration, dialing cadence, true carrier CLI/ANI, and carrier spoof flags stay on the call session.

Sherlock does not emit campaign links in v1. Watson emits `CampaignAssociation`: `call_id`, `campaign_id`, `association_score`, `reasons[]`, `feature_scores{}`. Each reason is an `AssociationReason` whose `field` is a Sherlock observation or inference kind and whose `value` is the Sherlock value that supported the link. `feature_scores` is a sparse map of those field names to Watson's weights. It is not a dense embedding, and Sherlock does not compute it.

### Tier A

Identity keys.

| Shape | Feature | What to score |
| --- | --- | --- |
| `Inference` | `claimed_company_normalized` | Lowercase company with legal suffixes removed. |
| `Inference` | `phone_e164` | E.164 number tagged callback, spoken, or spoken_cli. |
| `Inference` | `domain_registrable` | eTLD+1 from domain observations. |
| `Inference` | `email_domain_registrable` | eTLD+1 of an email host. |
| `Inference` | `opening_script_fingerprint` | Ordered tokens from the first caller turns. |
| `Inference` | `pretext_category_canonical` | Closed pretext enum. |
| `Inference` | `identifier_kind` | Label on a case, reference, or badge span. |
| `Observation` | `callback_numbers` | Raw callback span behind phone_e164. |
| `Observation` | `spoken_cli_claim` | Spoken calling-from number, not carrier CLI. |
| `Observation` | `case_or_reference_ids` | Raw identifier span behind identifier_kind. |
| `Observation` | `email_addresses` | Raw mailbox behind the email inferences. |
| `Observation` | `domains` | Raw host behind domain_registrable. |
| `Observation` | `urls` | Raw URL whose host is also a domain observation. |

### Tier B

Useful, and noisier than Tier A.

| Shape | Feature | What to score |
| --- | --- | --- |
| `Inference` | `script_phrase_normalized` | Lowercase punctuation-stripped phrase, original kept alongside. |
| `Inference` | `email_local_domain` | Local part and domain split. |
| `Observation` | `opening_script_text` | Raw text of caller turns 0, 1, and 2. |
| `Observation` | `ivr_menu_path` | Spoken order of a menu in one system segment. |
| `Observation` | `ivr_prompts` | Each press-N-for prompt. |
| `Observation` | `transfer_destination_claimed` | Org, desk, or number named at transfer. |
| `Observation` | `payment_methods` | Cash-out rail plus payment_method. |
| `Observation` | `remote_access_tools` | Named remote-control tool. |
| `Observation` | `script_phrases` | Raw script span behind script_phrase_normalized. |
| `Observation` | `spoofed_authority_claims` | Spoken authority clause. |
| `Observation` | `claimed_company` | Raw company span behind claimed_company_normalized. |

### Tier C

Context. Weak as a key by itself.

| Shape | Feature | What to score |
| --- | --- | --- |
| `Observation` | `script_language` | Locale when the script gives one. |
| `Observation` | `urgency_language` | Time pressure. |
| `Observation` | `threat_or_consequence_language` | Arrest, freeze, or lawsuit language. |
| `Observation` | `claimed_agent` | Persona name. |
| `Observation` | `claimed_department` | Pretext desk. |
| `Observation` | `fees` | Fee amount. |
| `Observation` | `loan_amounts` | Principal amount. |
| `Observation` | `rates` | Interest or APR. |
| `Observation` | `follow_up_promises` | Promise to call, email, or send a link. |
| `Observation` | `transfer_events` | The handoff itself. |
| `Observation` | `requested_information` | Data the caller asked for. |
| `Observation` | `spoken_numbers` | A phone that is not a callback or a spoken CLI. |
| `Observation` | `other` | Badge and leftover identifiers. |

`phone_e164.source_tag` is `callback`, `spoken`, or `spoken_cli`. `identifier_kind` is `ticket`, `case`, `claim`, `confirmation`, `reference`, `badge`, `ssn_last4`, or `account`. `script_language.locale` is `en`, `es`, or `other`. `opening_script_text.opening_turn_index` is 0, 1, or 2.
