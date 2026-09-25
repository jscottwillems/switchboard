"""Regex and lexicon extraction for indicators that are obvious in text.

Rules are conservative: a dollar amount without a fee or loan cue is skipped,
and a percent sign without an interest cue is skipped. That keeps precision
high. See `coverage.MODEL_GAPS` for what this module will not attempt.
"""

import re
from collections.abc import Callable
from urllib.parse import urlparse

from switchboard_intelligence.extraction import confidence
from switchboard_intelligence.extraction.lexicon import (
    DEPARTMENTS,
    ORGANIZATIONS,
    PAYMENT_PHRASES,
    REQUEST_CUES,
    REQUEST_TARGETS,
    SCRIPT_PHRASES,
    TRANSFER_PHRASES,
    URGENCY_PHRASES,
)
from switchboard_intelligence.extraction.normalize import (
    normalize_agent,
    normalize_domain,
    normalize_email,
    normalize_identifier,
    normalize_money,
    normalize_phone,
    normalize_phrase,
    normalize_rate,
    normalize_url,
)
from switchboard_intelligence.extraction.spans import (
    find_phrases,
    overlaps,
    span_timestamps,
    stable_id,
    word_bounded,
)
from switchboard_intelligence.schemas.observation import Observation, ObservationKind
from switchboard_intelligence.schemas.transcript import Transcript, TranscriptSegment

EXTRACTOR_NAME = "deterministic.rules/v1"

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[\s.\-]?)?(?:\(\s*\d{3}\s*\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\bhttps?://[^\s<>\"']+", re.IGNORECASE)
DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+(?:com|net|org|gov|edu|info|biz|us)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?")
RATE_RE = re.compile(
    r"\b\d{1,2}(?:\.\d{1,2})?\s?%|\b\d{1,2}(?:\.\d{1,2})?\s+percent\b",
    re.IGNORECASE,
)
RATE_CUE_RE = re.compile(r"\b(?:interest|apr|rate)\b", re.IGNORECASE)
FEE_CUE_RE = re.compile(r"\b(?:fees?|processing|activation|charges?)\b", re.IGNORECASE)
LOAN_CUE_RE = re.compile(
    r"\b(?:loan|qualify|qualified|approved|approval|principal|financing)\b",
    re.IGNORECASE,
)
CALLBACK_CUE_RE = re.compile(
    r"\b(?:call\s+us\s+back|call\s+back|callback|call\s+us\s+at|call\s+this\s+number|"
    r"dial|reach\s+us\s+at|our\s+number\s+is)\b",
    re.IGNORECASE,
)
COMPANY_CUE_RE = re.compile(
    r"\b(?:calling from(?: the)?|on behalf of(?: the)?|representing(?: the)?|"
    r"i am with(?: the)?|this is the)\b",
    re.IGNORECASE,
)
AGENT_NAME_RE = re.compile(r"\b[Mm]y name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
AGENT_TITLE_RE = re.compile(r"\b(?:Agent|Officer|Detective)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b")
OTHER_ID_RE = re.compile(
    r"\b(?:case|badge|reference|ticket|confirmation)\s+(?:number|id)\s*[:#]?\s*"
    r"([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)",
    re.IGNORECASE,
)
TRAILING_URL_PUNCT = ".,);:]\"'"

Normalizer = Callable[[str], str]


class DeterministicExtractor:
    """Scan a transcript once and return anchored observations."""

    name = EXTRACTOR_NAME

    def extract(self, transcript: Transcript) -> list[Observation]:
        found: list[Observation] = []
        for segment in transcript.segments:
            found.extend(self._extract_segment(transcript.call_id, segment))
        return dedupe_observations(found)

    def _extract_segment(self, call_id: str, segment: TranscriptSegment) -> list[Observation]:
        text = segment.text
        observations: list[Observation] = []
        email_spans = [(match.start(), match.end()) for match in EMAIL_RE.finditer(text)]
        url_matches = [_trim_url(match) for match in URL_RE.finditer(text)]
        url_spans = [(start, end) for start, end in url_matches]
        masked = email_spans + url_spans

        for start, end in email_spans:
            observations.append(
                self._emit(
                    call_id,
                    segment,
                    ObservationKind.EMAIL_ADDRESSES,
                    start,
                    end,
                    "email",
                    confidence.EMAIL,
                    normalize_email,
                )
            )
            local_sep = text.find("@", start, end)
            host_start = local_sep + 1
            host = text[host_start:end]
            if DOMAIN_RE.fullmatch(host):
                observations.append(
                    self._emit(
                        call_id,
                        segment,
                        ObservationKind.DOMAINS,
                        host_start,
                        end,
                        "email_domain",
                        confidence.DOMAIN_FROM_EMAIL,
                        normalize_domain,
                    )
                )

        for start, end in url_matches:
            url = text[start:end]
            observations.append(
                self._emit(
                    call_id,
                    segment,
                    ObservationKind.URLS,
                    start,
                    end,
                    "url",
                    confidence.URL,
                    normalize_url,
                )
            )
            host_span = _host_span(url)
            if host_span is not None:
                host_start, host_end = host_span
                observations.append(
                    self._emit(
                        call_id,
                        segment,
                        ObservationKind.DOMAINS,
                        start + host_start,
                        start + host_end,
                        "url_domain",
                        confidence.DOMAIN_FROM_URL,
                        normalize_domain,
                    )
                )

        for match in DOMAIN_RE.finditer(text):
            if overlaps(match.start(), match.end(), masked):
                continue
            observations.append(
                self._emit(
                    call_id,
                    segment,
                    ObservationKind.DOMAINS,
                    match.start(),
                    match.end(),
                    "bare_domain",
                    confidence.BARE_DOMAIN,
                    normalize_domain,
                )
            )

        previous_phone_end = 0
        for match in PHONE_RE.finditer(text):
            window_start = max(previous_phone_end, match.start() - 80)
            window = text[window_start:match.start()]
            kind = (
                ObservationKind.CALLBACK_NUMBERS
                if CALLBACK_CUE_RE.search(window)
                else ObservationKind.SPOKEN_NUMBERS
            )
            observations.append(
                self._emit(
                    call_id,
                    segment,
                    kind,
                    match.start(),
                    match.end(),
                    "phone",
                    confidence.PHONE,
                    normalize_phone,
                )
            )
            previous_phone_end = match.end()

        if RATE_CUE_RE.search(text):
            for match in RATE_RE.finditer(text):
                observations.append(
                    self._emit(
                        call_id,
                        segment,
                        ObservationKind.RATES,
                        match.start(),
                        match.end(),
                        "rate",
                        confidence.RATE,
                        normalize_rate,
                    )
                )

        for match in MONEY_RE.finditer(text):
            money_kind = _money_kind(text, match.start())
            if money_kind is None:
                continue
            observations.append(
                self._emit(
                    call_id,
                    segment,
                    money_kind,
                    match.start(),
                    match.end(),
                    "money",
                    confidence.MONEY,
                    normalize_money,
                )
            )

        observations.extend(
            self._phrases(
                call_id,
                segment,
                URGENCY_PHRASES,
                ObservationKind.URGENCY_LANGUAGE,
                "urgency",
                confidence.LEXICON,
            )
        )
        observations.extend(
            self._phrases(
                call_id,
                segment,
                SCRIPT_PHRASES,
                ObservationKind.SCRIPT_PHRASES,
                "script",
                confidence.LEXICON,
            )
        )
        observations.extend(
            self._phrases(
                call_id,
                segment,
                PAYMENT_PHRASES,
                ObservationKind.PAYMENT_METHODS,
                "payment",
                confidence.LEXICON,
            )
        )
        observations.extend(
            self._phrases(
                call_id,
                segment,
                DEPARTMENTS,
                ObservationKind.CLAIMED_DEPARTMENT,
                "department",
                confidence.LEXICON,
            )
        )
        observations.extend(
            self._phrases(
                call_id,
                segment,
                TRANSFER_PHRASES,
                ObservationKind.TRANSFER_EVENTS,
                "transfer",
                confidence.TRANSFER,
            )
        )
        if find_phrases(text, REQUEST_CUES):
            observations.extend(
                self._phrases(
                    call_id,
                    segment,
                    REQUEST_TARGETS,
                    ObservationKind.REQUESTED_INFORMATION,
                    "requested",
                    confidence.REQUESTED,
                )
            )
        observations.extend(self._companies(call_id, segment))
        observations.extend(self._agents(call_id, segment))
        observations.extend(self._identifiers(call_id, segment))
        return observations

    def _phrases(
        self,
        call_id: str,
        segment: TranscriptSegment,
        phrases: tuple[str, ...],
        kind: ObservationKind,
        rule: str,
        score: float,
    ) -> list[Observation]:
        return [
            self._emit(
                call_id,
                segment,
                kind,
                start,
                end,
                rule,
                score,
                normalize_phrase,
            )
            for start, end, _surface in find_phrases(segment.text, phrases)
        ]

    def _companies(self, call_id: str, segment: TranscriptSegment) -> list[Observation]:
        text = segment.text
        found: list[Observation] = []
        occupied: list[tuple[int, int]] = []
        organizations = sorted(ORGANIZATIONS, key=len, reverse=True)
        for cue in COMPANY_CUE_RE.finditer(text):
            window_end = min(len(text), cue.end() + 80)
            window = text[cue.end():window_end]
            for organization in organizations:
                match = re.search(rf"\b{re.escape(organization)}\b", window, re.IGNORECASE)
                if match is None:
                    continue
                start = cue.end() + match.start()
                end = cue.end() + match.end()
                if overlaps(start, end, occupied) or not word_bounded(text, start, end):
                    continue
                occupied.append((start, end))
                found.append(
                    self._emit(
                        call_id,
                        segment,
                        ObservationKind.CLAIMED_COMPANY,
                        start,
                        end,
                        "company",
                        confidence.COMPANY,
                        normalize_phrase,
                    )
                )
                break
        return found

    def _agents(self, call_id: str, segment: TranscriptSegment) -> list[Observation]:
        found: list[Observation] = []
        occupied: list[tuple[int, int]] = []
        for pattern in (AGENT_NAME_RE, AGENT_TITLE_RE):
            for match in pattern.finditer(segment.text):
                start, end = match.start(1), match.end(1)
                if overlaps(start, end, occupied):
                    continue
                occupied.append((start, end))
                found.append(
                    self._emit(
                        call_id,
                        segment,
                        ObservationKind.CLAIMED_AGENT,
                        start,
                        end,
                        "agent",
                        confidence.AGENT,
                        normalize_agent,
                    )
                )
        return found

    def _identifiers(self, call_id: str, segment: TranscriptSegment) -> list[Observation]:
        found: list[Observation] = []
        for match in OTHER_ID_RE.finditer(segment.text):
            identifier = match.group(1)
            if len(identifier) < 4 or not re.search(r"\d", identifier):
                continue
            found.append(
                self._emit(
                    call_id,
                    segment,
                    ObservationKind.OTHER,
                    match.start(1),
                    match.end(1),
                    "identifier",
                    confidence.OTHER_ID,
                    normalize_identifier,
                )
            )
        return found

    def _emit(
        self,
        call_id: str,
        segment: TranscriptSegment,
        kind: ObservationKind,
        char_start: int,
        char_end: int,
        rule: str,
        score: float,
        normalize: Normalizer,
    ) -> Observation:
        value = segment.text[char_start:char_end]
        normalized = normalize(value)
        start_timestamp, end_timestamp = span_timestamps(segment, char_start, char_end)
        observation_id = stable_id(
            "obs",
            f"{call_id}|{kind.value}|{segment.segment_id}|{normalized}|{char_start}",
        )
        return Observation(
            observation_id=observation_id,
            call_id=call_id,
            kind=kind,
            value=value,
            normalized_value=normalized,
            source=f"{self.name}#{rule}",
            transcript_segment_id=segment.segment_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            char_start=char_start,
            char_end=char_end,
            confidence=score,
        )


def _trim_url(match: re.Match[str]) -> tuple[int, int]:
    start, end = match.start(), match.end()
    text = match.string
    while end > start and text[end - 1] in TRAILING_URL_PUNCT:
        end -= 1
    return start, end


def _host_span(url: str) -> tuple[int, int] | None:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None or "." not in hostname:
        return None
    scheme_sep = url.lower().find("://")
    if scheme_sep < 0:
        return None
    rest = url[scheme_sep + 3 :]
    index = rest.lower().find(hostname.lower())
    if index < 0:
        return None
    absolute = scheme_sep + 3 + index
    return absolute, absolute + len(hostname)


def _nearest_cue_distance(text: str, pattern: re.Pattern[str], money_start: int) -> int | None:
    distances = [abs(match.start() - money_start) for match in pattern.finditer(text)]
    if not distances:
        return None
    return min(distances)


def _money_kind(text: str, money_start: int) -> ObservationKind | None:
    fee_distance = _nearest_cue_distance(text, FEE_CUE_RE, money_start)
    loan_distance = _nearest_cue_distance(text, LOAN_CUE_RE, money_start)
    if fee_distance is None and loan_distance is None:
        return None
    if fee_distance is None:
        return ObservationKind.LOAN_AMOUNTS
    if loan_distance is None:
        return ObservationKind.FEES
    if fee_distance <= loan_distance:
        return ObservationKind.FEES
    return ObservationKind.LOAN_AMOUNTS


def dedupe_observations(observations: list[Observation]) -> list[Observation]:
    """Keep one observation per segment, kind, and normalized value.

    The higher-confidence hit wins so a URL host outranks the same host
    repeated inside an email address in that segment.
    """
    best: dict[tuple[str, ObservationKind, str], Observation] = {}
    for observation in observations:
        key = (observation.transcript_segment_id, observation.kind, observation.normalized_value)
        current = best.get(key)
        if current is None or (observation.confidence, -observation.char_start) > (
            current.confidence,
            -current.char_start,
        ):
            best[key] = observation
    return sorted(
        best.values(),
        key=lambda item: (
            item.start_timestamp,
            item.transcript_segment_id,
            item.char_start,
            item.kind.value,
            item.value,
        ),
    )
