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
| 10 | `follow_up_promises` | A promise to call back, send a link, or follow up later. |
| 11 | `other` | Badge numbers and identifiers that are not case or reference ids. |

Rank 11 is the catch-all field, not one of the ten elicit priorities.

### Goal ids

Use the field strings above verbatim in `goals_completed` and `goals_remaining`. They are `ObservationKind` values. Do not invent parallel names.

`pretext_category` enum, stored on that observation and repeated in `normalized_value`: `tax`, `bank`, `warranty`, `debt`, `prize`, `tech_support`, `government`, `utility`, `other`. The free-text purpose is the observation `value` (the spoken purpose span), not a second goal id.

`payment_method` enum, only on `payment_methods`: `gift_card`, `wire`, `crypto`, `remote_access`, `bank_verify`, `other`.

### Ownership

Sherlock owns typed Observation, Inference, and Attribution, each observation grounded in a transcript span plus confidence. Loki does not emit those records and does not set an extraction confidence.

Optional soft handoff only, unverified breadcrumbs Sherlock may later check against the transcript:

```json
"elicited_hints": [
  {"goal": "callback_numbers", "surface_text": "call this number", "turn_index": 3}
]
```

`goal` is an `ObservationKind` value. Hints are not observations. Asking for a literal number, URL, host, email, or dollar amount still matters: the deterministic extractor only records obvious surface forms. See `docs/INTELLIGENCE.md`.
