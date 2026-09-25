"""Closed phrase lists used by the deterministic extractor.

Matching is case-insensitive and requires a word boundary on both ends.
Phrases are ASCII so casefold indexes line up with the original text.
"""

from switchboard_intelligence.schemas.observation import PaymentMethod, PretextCategory

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
    "do not tell anyone",
    "right away",
    "limited time",
    "expires today",
    "urgent matter",
)

THREAT_PHRASES: tuple[str, ...] = (
    "arrest warrant",
    "you will be arrested",
    "account will be frozen",
    "account will be suspended",
    "file a lawsuit",
    "legal action",
    "failure to comply",
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
    "remote session",
    "bank verification",
)

PAYMENT_METHOD_BY_PHRASE: dict[str, PaymentMethod] = {
    "gift card": PaymentMethod.GIFT_CARD,
    "prepaid card": PaymentMethod.GIFT_CARD,
    "green dot": PaymentMethod.GIFT_CARD,
    "wire transfer": PaymentMethod.WIRE,
    "western union": PaymentMethod.WIRE,
    "moneygram": PaymentMethod.WIRE,
    "bitcoin": PaymentMethod.CRYPTO,
    "cryptocurrency": PaymentMethod.CRYPTO,
    "remote session": PaymentMethod.REMOTE_ACCESS,
    "bank verification": PaymentMethod.BANK_VERIFY,
    "zelle": PaymentMethod.OTHER,
    "cash app": PaymentMethod.OTHER,
}

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

REMOTE_ACCESS_TOOLS: tuple[str, ...] = (
    "AnyDesk",
    "TeamViewer",
    "Splashtop",
    "LogMeIn",
    "Quick Assist",
    "Chrome Remote Desktop",
    "UltraViewer",
    "Zoho Assist",
)

FOLLOW_UP_PHRASES: tuple[str, ...] = (
    "i will call you back",
    "we will send you a link",
    "i will email the next steps",
    "a colleague will follow up",
)

# Spoken purpose after "the purpose of this call is". The value is this
# free-text phrase; the enum is the coarse class.
PURPOSE_CATEGORIES: dict[str, PretextCategory] = {
    "your tax compliance matter": PretextCategory.TAX,
    "a bank fraud alert": PretextCategory.BANK,
    "your auto warranty plan": PretextCategory.WARRANTY,
    "your outstanding loan debt": PretextCategory.DEBT,
    "your prize claim": PretextCategory.PRIZE,
    "a technical support alert": PretextCategory.TECH_SUPPORT,
    "a government benefits review": PretextCategory.GOVERNMENT,
    "your utility shutoff notice": PretextCategory.UTILITY,
    "your package delivery issue": PretextCategory.OTHER,
}
