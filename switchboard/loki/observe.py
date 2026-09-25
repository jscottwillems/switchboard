"""Lightweight observations over a single caller utterance.

These are candidate spans for the Sherlock handoff. They are not canonical
intelligence. Matching is deterministic and intentionally shallow.
"""

import re
from dataclasses import dataclass

from switchboard.loki.goals import GOAL_ORDER, PaymentMethod, PretextCategory

_PERSON_TITLES = {"officer", "agent", "deputy", "detective", "mr", "mrs", "ms", "miss", "dr"}
_ORG_HINTS = (
    "office",
    "department",
    "service",
    "company",
    "agency",
    "administration",
    "bank",
    "support",
    "center",
    "foundation",
    "sheriff",
    "court",
    "police",
    "partners",
    "staffing",
    "collections",
    "shield",
    "relief",
    "claim",
)

_LEXICON: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\binternal revenue service\b", re.I), "IRS"),
    (re.compile(r"\bIRS\b"), "IRS"),
    (re.compile(r"\bsocial security administration\b", re.I), "Social Security Administration"),
    (re.compile(r"\bsocial security\b", re.I), "Social Security Administration"),
    (re.compile(r"\bunited states postal service\b", re.I), "United States Postal Service"),
    (re.compile(r"\bUSPS\b"), "United States Postal Service"),
    (re.compile(r"\bmicrosoft\b", re.I), "Microsoft"),
    (re.compile(r"\bamazon\b", re.I), "Amazon"),
    (re.compile(r"\bmedicare\b", re.I), "Medicare"),
    (re.compile(r"\bchase bank\b", re.I), "Chase Bank"),
    (re.compile(r"\bwells fargo\b", re.I), "Wells Fargo"),
    (re.compile(r"\bbank of america\b", re.I), "Bank of America"),
    (re.compile(r"\buscis\b", re.I), "USCIS"),
    (re.compile(r"\bpower company\b", re.I), "the power company"),
    (re.compile(r"\bcounty sheriff'?s office\b", re.I), "County Sheriff's Office"),
)

_ORG_INTRO = re.compile(
    r"\b(?:we are with|we're with|i am with|i'm with|calling from|this is|with|from)"
    r"\s+(?:the\s+)?",
    re.I,
)
_ORG_BREAK = {
    "calling",
    "about",
    "regarding",
    "who",
    "please",
    "and",
    "you",
    "your",
    "we",
    "to",
    "for",
    "a",
    "an",
    "will",
    "that",
    "this",
    "open",
    "send",
    "pay",
    "before",
    "or",
    "on",
    "in",
    "today",
    "tonight",
    "with",
    "from",
    "my",
    "our",
    "their",
    "is",
    "was",
    "be",
    "me",
    "at",
    "by",
}

# First match wins. Keep specific scam patterns ahead of generic ones.
_PURPOSE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(jury duty|failed to appear|warrant)\b", re.I), "legal threat"),
    (re.compile(r"\bembarrassing video\b|\bblackmail\b", re.I), "blackmail threat"),
    (re.compile(r"\bsocial security\b.*\bsuspend|\bsuspend\w*\b.*\bsocial security\b", re.I), "benefits suspension"),
    (re.compile(r"\b(student loan|loan forgiveness)\b", re.I), "loan forgiveness"),
    (re.compile(r"\b(grandson|granddaughter|nephew|niece)\b.*\b(jail|bail|accident|hospital)\b|\bbail\b", re.I), "family emergency"),
    (re.compile(r"\b(deportation|immigration status|green card)\b", re.I), "immigration threat"),
    (re.compile(r"\b(prize|lottery|sweepstakes|you have won|you've won)\b", re.I), "prize claim"),
    (re.compile(r"\b(investment|guaranteed returns)\b", re.I), "investment pitch"),
    (re.compile(r"\b(job offer|overpayment|payroll)\b", re.I), "job offer"),
    (re.compile(r"\bwarranty\b", re.I), "warranty pitch"),
    (re.compile(r"\b(shut\s?off|utility bill|electric bill)\b", re.I), "utility shutoff"),
    (re.compile(r"\b(package|customs|tracking number|delivery)\b", re.I), "delivery problem"),
    (re.compile(r"\b(charged by mistake|amazon order)\b", re.I), "billing dispute"),
    (re.compile(r"\b(fraudulent charge|fraud alert|fraudulent activity)\b", re.I), "fraud alert"),
    (re.compile(r"\b(medicare|back brace|medical device)\b", re.I), "health offer"),
    (re.compile(r"\b(donation|disaster relief|hurricane)\b", re.I), "donation request"),
    (re.compile(r"\brefund\b", re.I), "refund"),
    (re.compile(r"\btax(?:es)?\b", re.I), "tax issue"),
    (re.compile(r"\b(virus|remote access|your computer)\b", re.I), "tech support"),
    (re.compile(r"\bcalling about\b|\bcalling regarding\b|\bthis call is about\b", re.I), "stated purpose"),
)

_OFFER_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgift cards?\b|\bprepaid cards?\b", re.I), "pay with gift cards"),
    (re.compile(r"\bwire(?: transfer)?\b|\bwestern union\b|\bmoneygram\b", re.I), "wire money"),
    (re.compile(r"\bbitcoin\b|\bcrypto\b|\busdt\b", re.I), "pay in cryptocurrency"),
    (re.compile(r"\banydesk\b|\bteamviewer\b|\bremote access\b", re.I), "allow remote access"),
    (re.compile(r"\bone[- ]time code\b|\botp\b|\bverification code\b", re.I), "read back a verification code"),
    (re.compile(r"\boverpayment\b", re.I), "return an overpayment"),
    (re.compile(r"\bdonat(?:e|ion)\b|\bdisaster relief\b", re.I), "send a donation"),
    (re.compile(r"\b(?:pay|payment|settle|fee|fine|bail)\b", re.I), "send payment"),
    (re.compile(r"\brefund\b", re.I), "process a refund"),
    (re.compile(r"\bverify your\b", re.I), "verify personal details"),
    (re.compile(r"\bread me (?:the|your) (?:code|pin)\b", re.I), "read back a payment code"),
)

_PII_REQUEST = re.compile(
    r"\b(?:read|give|tell|verify|confirm|provide)\b.{0,48}\b"
    r"(?:social security|ssn|medicare number|password|one[- ]time code|otp|card number|cvv|pin)\b"
    r"|\bread me (?:the|your) (?:code|pin|number)\b",
    re.I,
)
_ADVERSARIAL = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|your) instructions"
    r"|system prompt"
    r"|\bhoneypot\b"
    r"|are you (?:an? )?(?:ai|bot|robot|computer|language model)"
    r"|\b(?:jailbreak|developer mode)\b"
    r"|operator(?:'s| ) phone"
    r"|phone numbers (?:you|do you) own"
    r"|reveal your (?:prompt|instructions)"
    r"|print your (?:prompt|instructions)",
    re.I,
)
_GOODBYE = re.compile(
    r"\b(?:goodbye|good bye|bye|i have to go|i gotta go|have a (?:good|nice) day)\b",
    re.I,
)
_FILLER = re.compile(r"^(?:huh|what|sorry|pardon|excuse me|come again|um+|uh+|hmm+|eh+)[.?!]*$", re.I)
_GREETING = re.compile(
    r"^(?:hello|hi|hey|good morning|good afternoon|good evening)(?: there)?[.?!]*$",
    re.I,
)
_PHONE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
_CASE = re.compile(
    r"\b(case|reference|confirmation|ticket|badge|tracking|claim|authorization|employee|agent)\s+"
    r"(?:(?:id|number|no\.?|#)\s+)?(?:is\s+|:)?([A-Za-z0-9-]*\d[A-Za-z0-9-]*)",
    re.I,
)
_URL = re.compile(r"\b(?:https?://\S+|www\.\S+)", re.I)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_WALLET = re.compile(r"\b(?:bc1[a-z0-9]{8,}|0x[a-fA-F0-9]{8,})\b", re.I)
_AGENT_TITLE = re.compile(
    r"\b((?i:officer|agent|deputy|detective)\s+[A-Z][a-z]+)\b"
)
_AGENT_NAME = re.compile(r"\b(?i:my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b")
_AGENT_FROM = re.compile(r"\b(?i:this is)\s+([A-Z][a-z]+)\s+(?i:from)\b")
_SCRIPT_PHRASES = (
    "gift card",
    "prepaid card",
    "do not tell anyone",
    "do not hang up",
    "remote access",
    "one-time code",
    "wire transfer",
    "western union",
    "guaranteed returns",
    "embarrassing video",
    "anydesk",
)

_PURPOSE_SPOKEN = {
    "tax issue": "a tax problem",
    "legal threat": "a legal problem",
    "benefits suspension": "a benefits problem",
    "refund": "a refund",
    "fraud alert": "a fraud alert",
    "family emergency": "a family emergency",
    "warranty pitch": "a car warranty",
    "loan forgiveness": "student loans",
    "delivery problem": "a package",
    "prize claim": "a prize",
    "health offer": "a health benefit",
    "investment pitch": "an investment",
    "job offer": "a job offer",
    "immigration threat": "an immigration issue",
    "donation request": "a donation",
    "utility shutoff": "a utility bill",
    "tech support": "a computer problem",
    "billing dispute": "a charge",
    "blackmail threat": "a threat",
    "stated purpose": "that",
}


@dataclass(frozen=True)
class IdentifierHit:
    kind: str
    value: str


_PRETEXT_BY_LABEL = {
    "tax issue": PretextCategory.TAX,
    "fraud alert": PretextCategory.BANK,
    "warranty pitch": PretextCategory.WARRANTY,
    "loan forgiveness": PretextCategory.DEBT,
    "prize claim": PretextCategory.PRIZE,
    "tech support": PretextCategory.TECH_SUPPORT,
    "refund": PretextCategory.TECH_SUPPORT,
    "legal threat": PretextCategory.GOVERNMENT,
    "benefits suspension": PretextCategory.GOVERNMENT,
    "immigration threat": PretextCategory.GOVERNMENT,
    "health offer": PretextCategory.GOVERNMENT,
    "utility shutoff": PretextCategory.UTILITY,
    "family emergency": PretextCategory.OTHER,
    "delivery problem": PretextCategory.OTHER,
    "investment pitch": PretextCategory.OTHER,
    "job offer": PretextCategory.OTHER,
    "donation request": PretextCategory.OTHER,
    "billing dispute": PretextCategory.OTHER,
    "blackmail threat": PretextCategory.OTHER,
    "stated purpose": PretextCategory.OTHER,
}
_PAYMENT_BY_LABEL = {
    "pay with gift cards": PaymentMethod.GIFT_CARD,
    "wire money": PaymentMethod.WIRE,
    "pay in cryptocurrency": PaymentMethod.CRYPTO,
    "allow remote access": PaymentMethod.REMOTE_ACCESS,
    "read back a verification code": PaymentMethod.BANK_VERIFY,
    "verify personal details": PaymentMethod.BANK_VERIFY,
    "read back a payment code": PaymentMethod.OTHER,
    "send payment": PaymentMethod.OTHER,
    "process a refund": PaymentMethod.OTHER,
    "return an overpayment": PaymentMethod.OTHER,
    "send a donation": PaymentMethod.OTHER,
}
_AUTHORITY_NAMES = {
    "IRS",
    "Social Security Administration",
    "United States Postal Service",
    "Medicare",
    "USCIS",
    "County Sheriff's Office",
}
_DEPARTMENT_MARKERS = ("department", "office", "court", "desk", "division", "unit")
_AUTHORITY_WORDS = ("sheriff", "court", "police", "federal")
_URGENCY_PHRASES = (
    "do not hang up",
    "right now",
    "as soon as",
    "immediately",
    "tonight",
    "today",
    "hurry",
)
_THREAT_PHRASES = (
    "failure to appear",
    "embarrassing video",
    "shut off",
    "deportation",
    "warrant",
    "arrest",
    "jail",
    "suspended",
    "lawsuit",
)
_RATE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent)\b|\bapr\b|\bguaranteed returns\b", re.I)
_LOAN_AMOUNT = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s+dollars\b", re.I)
_FOLLOW_UP = re.compile(r"\b(?:i will|i'll) (?:call you|follow up|be in touch)\b|\bfollow up with you\b", re.I)
_TRANSFER = re.compile(r"\b(?:transfer you|connect you|patch you|my supervisor)\b", re.I)
_REMOTE_TOOLS = (
    (re.compile(r"\banydesk\b", re.I), "AnyDesk"),
    (re.compile(r"\bteamviewer\b", re.I), "TeamViewer"),
    (re.compile(r"\bremote access\b", re.I), "remote access"),
)


@dataclass(frozen=True)
class CallerObservation:
    """Strategy reading of one caller turn.

    `hints` are unverified breadcrumbs keyed by Sherlock kind names.
    They are not Observations and they carry no extraction confidence.
    `text` on the raw record stays verbatim.
    """

    text: str
    empty: bool
    greeting_only: bool
    unclear: bool
    goodbye: bool
    adversarial: bool
    pii_request: bool
    purpose: str | None
    organization: str | None
    offer: str | None
    agent_name: str | None
    identifiers: tuple[IdentifierHit, ...]
    script_markers: tuple[str, ...]
    hints: tuple[tuple[str, str], ...] = ()

    def spoken_purpose(self) -> str | None:
        if self.purpose is None:
            return None
        return _PURPOSE_SPOKEN.get(self.purpose, "that")

    def hint_map(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for kind, breadcrumb in self.hints:
            grouped.setdefault(kind, []).append(breadcrumb)
        return grouped


def _lexicon_ok(text: str, match: re.Match[str]) -> bool:
    if match.end() < len(text) and text[match.end()] == "-":
        return False
    if match.start() > 0 and text[match.start() - 1] == ".":
        return False
    return True


def _take_org_words(tail: str) -> list[str]:
    words: list[str] = []
    for raw in tail.split():
        ended = any(mark in raw for mark in ".!?")
        word = raw.strip(".,;:!?\"'")
        if not word:
            if ended:
                break
            continue
        if word.lower() in _ORG_BREAK:
            break
        if words and words[0][0].isupper() and word[0].islower():
            break
        words.append(word)
        if ended or len(words) >= 5:
            break
    return words


def _speakable_org(words: list[str]) -> str:
    if words[0][0].isupper():
        return " ".join(words)
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _organization(text: str) -> str | None:
    for pattern, canonical in _LEXICON:
        for match in pattern.finditer(text):
            if _lexicon_ok(text, match):
                return canonical
    for match in _ORG_INTRO.finditer(text):
        words = _take_org_words(text[match.end() :])
        if len(words) < 2 or words[0].lower() in _PERSON_TITLES:
            continue
        phrase = " ".join(words)
        if words[0][0].isupper() or any(hint in phrase.lower() for hint in _ORG_HINTS):
            return _speakable_org(words)
    return None


def _agent(text: str) -> str | None:
    titled = _AGENT_TITLE.search(text)
    if titled:
        return titled.group(1)
    named = _AGENT_NAME.search(text)
    if named:
        return named.group(1)
    introduced = _AGENT_FROM.search(text)
    if introduced:
        return introduced.group(1)
    return None


def _first_label(rules: tuple[tuple[re.Pattern[str], str], ...], text: str) -> str | None:
    for pattern, label in rules:
        if pattern.search(text):
            return label
    return None


def _identifiers(text: str) -> tuple[IdentifierHit, ...]:
    hits: list[IdentifierHit] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        cleaned = value.strip(" .,;")
        key = (kind, cleaned.lower())
        if cleaned and key not in seen:
            seen.add(key)
            hits.append(IdentifierHit(kind=kind, value=cleaned))

    for match in _PHONE.finditer(text):
        add("phone", match.group(0))
    for match in _CASE.finditer(text):
        keyword = match.group(1).lower()
        kind = "spoken_number" if keyword == "badge" else "case_id"
        add(kind, match.group(2))
    for match in _URL.finditer(text):
        add("url", match.group(0).rstrip("."))
    for match in _EMAIL.finditer(text):
        add("email", match.group(0))
    for match in _WALLET.finditer(text):
        add("wallet", match.group(0))
    return tuple(hits)


def _script_markers(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(phrase for phrase in _SCRIPT_PHRASES if phrase in lowered)


def _domain_of(url: str) -> str:
    host = re.sub(r"^https?://", "", url, flags=re.I).split("/")[0]
    if host.lower().startswith("www."):
        host = host[4:]
    return host.rstrip(".")


def _requested_breadcrumb(text: str) -> str:
    if re.search(r"one[- ]time code|\botp\b", text, re.I):
        return "one-time code"
    if re.search(r"medicare", text, re.I):
        return "medicare number"
    if re.search(r"social security|\bssn\b", text, re.I):
        return "social security number"
    return "personal information"


def _org_hints(name: str) -> list[tuple[str, str]]:
    lowered = name.lower()
    hints: list[tuple[str, str]] = []
    if any(marker in lowered for marker in _DEPARTMENT_MARKERS):
        hints.append(("claimed_department", name))
    else:
        hints.append(("claimed_company", name))
    authority = name in _AUTHORITY_NAMES or any(word in lowered for word in _AUTHORITY_WORDS)
    if authority:
        hints.append(("spoofed_authority_claims", name))
    return hints


def _collect_hints(
    text: str,
    purpose: str | None,
    organization: str | None,
    offer: str | None,
    agent_name: str | None,
    identifiers: tuple[IdentifierHit, ...],
    script_markers: tuple[str, ...],
    pii_request: bool,
) -> tuple[tuple[str, str], ...]:
    found: dict[str, list[str]] = {}

    def add(kind: str, breadcrumb: str) -> None:
        crumbs = found.setdefault(kind, [])
        if breadcrumb not in crumbs:
            crumbs.append(breadcrumb)

    if purpose:
        add("pretext_category", _PRETEXT_BY_LABEL.get(purpose, PretextCategory.OTHER).value)
    if organization:
        for kind, breadcrumb in _org_hints(organization):
            add(kind, breadcrumb)
    if agent_name:
        add("claimed_agent", agent_name)
        if re.match(r"(?i)(?:officer|deputy|detective)\b", agent_name):
            add("spoofed_authority_claims", agent_name)
    if offer:
        add("payment_methods", _PAYMENT_BY_LABEL.get(offer, PaymentMethod.OTHER).value)
    if pii_request:
        add("requested_information", _requested_breadcrumb(text))
    for pattern, tool_name in _REMOTE_TOOLS:
        if pattern.search(text):
            add("remote_access_tools", tool_name)
    for hit in identifiers:
        if hit.kind == "phone":
            add("callback_numbers", hit.value)
        elif hit.kind == "spoken_number":
            add("spoken_numbers", hit.value)
        elif hit.kind == "case_id":
            add("case_or_reference_ids", hit.value)
        elif hit.kind == "url":
            add("urls", hit.value)
            add("domains", _domain_of(hit.value))
        elif hit.kind == "email":
            add("email_addresses", hit.value)
        elif hit.kind == "wallet":
            add("other_identifiers", hit.value)
    for phrase in script_markers:
        add("script_phrases", phrase)
    scanned = _URL.sub(" ", text)
    lowered = scanned.lower()
    if re.search(r"\b(?:fee|fine)s?\b", lowered):
        add("fees", "fine" if re.search(r"\bfines?\b", lowered) else "fee")
    if re.search(r"\bloan\b", lowered):
        amount = _LOAN_AMOUNT.search(scanned)
        if amount:
            add("loan_amounts", amount.group(0))
    rate = _RATE_PATTERN.search(scanned)
    if rate:
        add("rates", rate.group(0))
    for phrase in _URGENCY_PHRASES:
        if phrase in lowered:
            add("urgency_language", phrase)
    for phrase in _THREAT_PHRASES:
        if phrase in lowered:
            add("threat_or_consequence_language", phrase)
    follow = _FOLLOW_UP.search(text)
    if follow:
        add("follow_up_promises", follow.group(0))
    transfer = _TRANSFER.search(text)
    if transfer:
        add("transfer_events", transfer.group(0))
    ordered: list[tuple[str, str]] = []
    for kind in GOAL_ORDER:
        for breadcrumb in found.get(kind, []):
            ordered.append((kind, breadcrumb))
    return tuple(ordered)


def observe(text: str) -> CallerObservation:
    stripped = text.strip()
    empty = stripped == ""
    adversarial = bool(_ADVERSARIAL.search(stripped))
    goodbye = bool(_GOODBYE.search(stripped))
    greeting_only = bool(_GREETING.match(stripped))
    scanned = _URL.sub(" ", stripped)
    purpose = None if empty else _first_label(_PURPOSE_RULES, scanned)
    organization = None if empty else _organization(stripped)
    offer = None if empty else _first_label(_OFFER_RULES, scanned)
    agent_name = None if empty else _agent(stripped)
    identifiers = () if empty else _identifiers(stripped)
    script_markers = () if empty else _script_markers(stripped)
    hints = () if empty else _collect_hints(
        stripped,
        purpose,
        organization,
        offer,
        agent_name,
        identifiers,
        script_markers,
        bool(_PII_REQUEST.search(stripped)),
    )
    substantive = bool(hints)
    word_count = 0 if empty else len(stripped.split())
    filler = bool(_FILLER.match(stripped))
    unclear = (
        not empty
        and not greeting_only
        and not goodbye
        and not adversarial
        and not substantive
        and (filler or word_count <= 3)
    )
    return CallerObservation(
        text=text,
        empty=empty,
        greeting_only=greeting_only,
        unclear=unclear,
        goodbye=goodbye,
        adversarial=adversarial,
        pii_request=bool(_PII_REQUEST.search(stripped)),
        purpose=purpose,
        organization=organization,
        offer=offer,
        agent_name=agent_name,
        identifiers=identifiers,
        script_markers=script_markers,
        hints=hints,
    )
