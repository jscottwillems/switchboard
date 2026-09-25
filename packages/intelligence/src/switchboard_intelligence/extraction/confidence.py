"""Explicit rule confidences for deterministic extraction and rule inferences.

These are not learned scores. They record how reliable the author considers
each rule family to be when the pattern matches.
"""

PHONE = 0.97
EMAIL = 0.98
URL = 0.96
DOMAIN_FROM_URL = 0.95
DOMAIN_FROM_EMAIL = 0.90
BARE_DOMAIN = 0.86
MONEY = 0.93
RATE = 0.94
LEXICON = 0.90
COMPANY = 0.88
AGENT = 0.84
REQUESTED = 0.87
OTHER_ID = 0.92
CASE_ID = 0.92
THREAT = 0.90
REMOTE_ACCESS = 0.93
SPOOF = 0.86
FOLLOW_UP = 0.90
PRETEXT = 0.90
THREATENED_CONSEQUENCE = 0.81
TRANSFER = 0.91

IMPERSONATED_ORGANIZATION = 0.84
PAYMENT_RAIL = 0.86
DATA_TARGET = 0.83
PRESSURE_TACTIC = 0.80
OFFER_TERMS = 0.82
CALLBACK_CHANNEL = 0.88
