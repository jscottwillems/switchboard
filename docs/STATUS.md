# STATUS

ATLAS owns the full status-doc structure. This file only carries Sherlock's handoff so Loki is not blocked on that document. Fold this section into ATLAS's status doc when it exists. Do not treat the headings below as the approved cross-team status schema.

## HANDOFF — Sherlock → Loki

During a live call, elicit the observation fields in this order. Infrastructure and cash-out come first. Pitch color comes last because callers usually volunteer it.

| Rank | Field | Why Loki should elicit it |
| --- | --- | --- |
| 1 | `callback_numbers` | Direct callable infrastructure if the session drops. |
| 2 | `payment_methods` | Cash-out rail that types the scam and the money path. |
| 3 | `urls` | Campaign site or payment page, often unique to a kit. |
| 4 | `domains` | Spoken or partial host when they will not give a full URL. |
| 5 | `email_addresses` | Contact point for documents, receipts, or follow-up. |
| 6 | `requested_information` | The data they are trying to harvest. |
| 7 | `claimed_company` | Who they want the target to believe is calling. |
| 8 | `claimed_department` | The pretext desk inside that organization. |
| 9 | `claimed_agent` | The alias or persona name they are using. |
| 10 | `fees` | The amount they want paid and the advance-fee ask. |
| 11 | `loan_amounts` | The offered or approved principal they are pitching. |
| 12 | `rates` | The interest rate or APR attached to the offer. |
| 13 | `other` | Case, badge, ticket, or reference identifiers for clustering. |
| 14 | `spoken_numbers` | Any other phone number they mention. |
| 15 | `transfer_events` | Accept a transfer and mark the handoff to a closer. |
| 16 | `script_phrases` | Let the pitch play; these cluster campaigns but are rarely elicited. |
| 17 | `urgency_language` | Ask how soon they need a decision so the deadline is explicit. |

Ask in words that produce a literal span: a phone number in digits, a full URL, a dotted host, an email address, or a dollar amount next to "fee" or "loan". Sherlock's current extractor records those surface forms. Paraphrases, numbers spoken as words, and hosts spoken as "dot com" stay empty until model extraction is connected. See `docs/INTELLIGENCE.md`.
