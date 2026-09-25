# Switchboard

Project Switchboard is an AI scam-call honeypot. Shared architecture documents are owned by ATLAS and are not in this repository yet.

Sherlock, the intelligence slice, lives in [`packages/intelligence`](packages/intelligence). It turns a transcript into observations, inferences, and, once a campaign corpus exists, attributions.

- [docs/INTELLIGENCE.md](docs/INTELLIGENCE.md) describes observation vs inference vs attribution and how extraction works.
- [docs/STATUS.md](docs/STATUS.md) is Sherlock's handoff to Loki: which fields to elicit, in rank order.
