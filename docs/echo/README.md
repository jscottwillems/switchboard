# ECHO

Media gateway notes. The behavioral contract is the "ECHO media requirements" section of `docs/API_CONTRACTS.md`. Tickets and the latest handoff are in `docs/STATUS.md`.

Wire audio is `audio/pcmu` or `audio/pcm`. The MVP telephony default is `audio/pcmu`, 8000 Hz, mono. `audio/x-mulaw` is rejected on `switchboard.media.v1`.

`MockTts` returns one 160-byte PCMU frame for non-empty text. The socket validates tokens and frames (SB-004). It does not yet run STT (SB-005) or speak back on the socket (SB-008).
