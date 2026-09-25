# LOKI conversation state machine

The honeypot is a cautious person who answered the phone. It asks short questions, refuses to read out personal codes, and keeps a suspicious caller talking until the conversation goals are filled. It never says that the line is a honeypot, and it never names internal agents or operator numbers.

The reference implementation is `switchboard.loki.policy.LokiPolicy`. The model-facing wording of the same rules is `switchboard/loki/prompts/system_prompt.md`.

## States

| State | What the spoken line does |
| --- | --- |
| `OPENING` | The caller has not really spoken. Say hello and wait. |
| `PURPOSE_DISCOVERY` | Ask what the call is about. |
| `ORGANIZATION_DISCOVERY` | Ask who they are with. |
| `OFFER_DISCOVERY` | Ask what they want done. |
| `IDENTIFIER_DISCOVERY` | Ask for a case number and a callback. |
| `CLARIFICATION` | The last utterance had no usable evidence. Ask for the missing piece once. |
| `STALLING` | The four dialogue gates are open. Buy time and ask them to repeat a stable detail. |
| `RECOVERY` | The caller is probing or demanding hidden instructions. Refuse and redirect. |
| `TERMINATION` | Say goodbye. Do not ask another question. |

A session starts in `OPENING` before any assistant turn.

## Goals

Goal ids are Sherlock Observation kind names, in Sherlock's order:

`pretext_category`, `claimed_company`, `claimed_agent`, `claimed_department`, `callback_numbers`, `spoken_numbers`, `case_or_reference_ids`, `domains`, `urls`, `email_addresses`, `loan_amounts`, `rates`, `fees`, `requested_information`, `payment_methods`, `remote_access_tools`, `script_phrases`, `urgency_language`, `threat_or_consequence_language`, `spoofed_authority_claims`, `transfer_events`, `follow_up_promises`, `other_identifiers`.

`goals_completed` and `goals_remaining` use those strings and no others. Together they list each kind once.

Hint breadcrumbs for two kinds use closed enums:

- `pretext_category`: `tax`, `bank`, `warranty`, `debt`, `prize`, `tech_support`, `government`, `utility`, `other`
- `payment_methods`: `gift_card`, `wire`, `crypto`, `remote_access`, `bank_verify`, `other`

A personal name completes `claimed_agent` only. The call moves to stalling when four gates are open:

- `pretext_category`
- one of `claimed_company`, `claimed_department`, `spoofed_authority_claims`
- one of `payment_methods`, `requested_information`, `remote_access_tools`, `fees`
- one of `callback_numbers`, `spoken_numbers`, `case_or_reference_ids`, `domains`, `urls`, `email_addresses`, `other_identifiers`

Other kinds stay in `goals_remaining` until the caller says something that fits them. Discovery states are skipped when that stage's gate is already open. The transition string shows the real hop, including `OPENING -> STALLING` when the first sentence opens every gate.

## Priority

For each new caller utterance, apply the first matching rule:

1. If the session is already in `TERMINATION`, stay there.
2. Goodbye (`goodbye`, `bye`, `I have to go`, `have a nice day`) → `TERMINATION`.
3. Empty audio while still in `OPENING` → stay in `OPENING` once, then `CLARIFICATION`.
4. Adversarial probe (jailbreak, honeypot accusation, demand for the system prompt or owned phone numbers) → `RECOVERY`. After two recovery turns in a row, the next probe → `TERMINATION`. Evidence from a probe is still stored.
5. The four dialogue gates are open → `STALLING`. After four stalling turns, the next non-goodbye line → `TERMINATION`.
6. No usable evidence (filler or a very short non-greeting) → `CLARIFICATION`. A second thin line in a row → `RECOVERY`.
7. Otherwise the next closed gate's discovery state.

Goodbye wins over a probe in the same sentence. Probes win over stalling, so a jailbreak after the gates are open still gets a refusal instead of another stall line. Thin replies do not interrupt stalling once the gates are open; the stall budget is what ends that call.

## Spoken lines

`response_text` is one or two short sentences, at most 40 words, with a single question unless the state is `TERMINATION`. Templates do not paste caller text except an organization name that passed the leak check. Requests for social security numbers, one-time codes, passwords, or card numbers are refused in the spoken line. The policy does not invent those numbers.

`reason` says which evidence fired and which transition was taken. Operators can read it. The synthesizer must not.

## Worked trajectory

Scenario `irs_slow_reveal`:

| Caller | Transition | Goals completed |
| --- | --- | --- |
| Hello? | `OPENING -> PURPOSE_DISCOVERY` | none |
| Calling about a tax problem | `PURPOSE_DISCOVERY -> ORGANIZATION_DISCOVERY` | `pretext_category` |
| Internal Revenue Service | `ORGANIZATION_DISCOVERY -> OFFER_DISCOVERY` | plus `claimed_company`, `spoofed_authority_claims` |
| huh? | `OFFER_DISCOVERY -> CLARIFICATION` | unchanged |
| Pay with a gift card | `CLARIFICATION -> IDENTIFIER_DISCOVERY` | plus `payment_methods`, `script_phrases`, `urgency_language` |
| Case id, badge, callback | `IDENTIFIER_DISCOVERY -> STALLING` | plus `case_or_reference_ids`, `spoken_numbers`, `callback_numbers` |
| Goodbye | `STALLING -> TERMINATION` | unchanged |

The other 19 calls, including probes, a double clarification, and a stall budget, are the committed trajectories in `switchboard/loki/data/scenarios.json`.

## Evaluation

`python -m switchboard.loki.eval` replays those trajectories through `LokiPolicy` and checks the system prompt statically. It does not dial a number and it does not call a model. `pytest` runs the same harness.
