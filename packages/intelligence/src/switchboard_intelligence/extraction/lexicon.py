"""Closed phrase lists used by the deterministic extractor.

Matching is case-insensitive and requires a word boundary on both ends.
Phrases are ASCII so casefold indexes line up with the original text.
"""

ORGANIZATIONS: tuple[str, ...] = (
    "Internal Revenue Service",
    "Social Security Administration",
    "Medicare",
    "Microsoft",
    "Apple",
    "Amazon",
    "Bank of America",
    "Wells Fargo",
    "Geek Squad",
    "Publishers Clearing House",
    "Federal Student Aid",
    "PayPal",
    "Citibank",
    "National Grid",
)

DEPARTMENTS: tuple[str, ...] = (
    "fraud department",
    "legal department",
    "claims department",
    "warranty department",
    "loan servicing department",
    "verification department",
    "security department",
    "benefits department",
    "collections department",
    "awards department",
)

URGENCY_PHRASES: tuple[str, ...] = (
    "act immediately",
    "final notice",
    "within 24 hours",
    "last chance",
    "legal action",
    "do not tell anyone",
    "right away",
    "limited time",
    "expires today",
    "failure to comply",
    "arrest warrant",
    "account will be suspended",
    "urgent matter",
)

SCRIPT_PHRASES: tuple[str, ...] = (
    "this is an important message",
    "your account has been compromised",
    "you have been selected",
    "press 1 to speak with a representative",
    "this call is being recorded",
    "extended vehicle warranty",
    "student loan forgiveness",
    "refund is waiting",
    "verify your identity",
    "your package could not be delivered",
    "you have won a prize",
)

PAYMENT_PHRASES: tuple[str, ...] = (
    "gift card",
    "wire transfer",
    "bitcoin",
    "western union",
    "moneygram",
    "zelle",
    "cash app",
    "prepaid card",
    "green dot",
    "cryptocurrency",
)

REQUEST_TARGETS: tuple[str, ...] = (
    "social security number",
    "date of birth",
    "bank account number",
    "routing number",
    "credit card number",
    "one-time password",
    "driver's license number",
    "medicare number",
)

TRANSFER_PHRASES: tuple[str, ...] = (
    "let me transfer you",
    "i am transferring you",
    "transferring you now",
    "connecting you to",
    "please hold while i connect you",
)

# Cue must appear in the same segment as a request target.
REQUEST_CUES: tuple[str, ...] = (
    "provide your",
    "confirm your",
    "read me your",
    "what is your",
    "need your",
    "tell me your",
    "verify your",
)
