# ECHO

Media gateway notes. The behavioral contract is the "ECHO media requirements" section of `docs/API_CONTRACTS.md`. Tickets and the latest handoff are in `docs/STATUS.md`.

Wire audio is `audio/pcmu` or `audio/pcm`. The MVP telephony default is `audio/pcmu`, 8000 Hz, mono. `audio/x-mulaw` is rejected on `switchboard.media.v1`.

`MockTts` returns one 160-byte PCMU frame for non-empty text. `MockStt` returns one final segment for `MOCK_STT_FIXTURE_FRAME`, and the socket publishes `speech.segment.final` (SB-005). The socket does not speak back yet (SB-008).
