from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    category: str
    explanation: str


_JOB_TERMS = re.compile(
    r"\b(?:hiring|job|position|employment|recruiting|work opportunity|"
    r"remote work|onboarding|vacancy|apply for)\b",
    re.IGNORECASE,
)
_ROLE_OR_DUTY_TERMS = re.compile(
    r"\b(?:assistant|analyst|cashier|tutor|designer|developer|engineer|"
    r"receptionist|representative|coordinator|intern|driver|deliver|teach|"
    r"manage|maintain|support|research|sales|data entry|customer service|"
    r"responsibilit(?:y|ies)|duties|tasks|shift|schedule)\b",
    re.IGNORECASE,
)
_URGENCY = re.compile(
    r"\b(?:reply now|act now|immediately|urgent|today|within\s+"
    r"\d+\s+(?:hours?|days?)|next\s+24\s+hours|secure your position|"
    r"limited[- ]time)\b",
    re.IGNORECASE,
)
_UPFRONT_PAYMENT = re.compile(
    r"\b(?:"
    r"(?:deposit|fee|charge|payment)\s+(?:of\s+)?\$?\d[\d,.]*|"
    r"\$?\d[\d,.]*\s+(?:deposit|fee|charge)|"
    r"(?:pay|send|purchase|buy)[^\n.!?]{0,35}"
    r"(?:fee|deposit|training|equipment|activation)"
    r")\b",
    re.IGNORECASE,
)
_HIGH_DAILY_EARNINGS = re.compile(
    r"(?:earn|earning|make|up to|pay|salary|income)[^\n.!?]{0,40}"
    r"\$\s?([\d,]+)[^\n.!?]{0,20}(?:per day|/day|a day|daily)",
    re.IGNORECASE,
)
_HIGH_EARNINGS_REVERSED = re.compile(
    r"\$\s?([\d,]+)\s*(?:per day|/day|a day|daily)",
    re.IGNORECASE,
)
_EMPLOYER_NAME = re.compile(
    r"\b(?:at|from|with|for|join)\s+"
    r"([A-Z][A-Za-z0-9&'.-]*(?:\s+[A-Z][A-Za-z0-9&'.-]*){0,2})"
)


def _contains_high_daily_earnings(text: str) -> bool:
    for pattern in (_HIGH_DAILY_EARNINGS, _HIGH_EARNINGS_REVERSED):
        for match in pattern.finditer(text):
            try:
                amount = int(match.group(1).replace(",", ""))
            except ValueError:
                continue
            if amount >= 200:
                return True
    return False


def explain_message(
    text: str,
    *,
    first_contact: bool,
    saved_contact: bool,
    sender_metadata: dict[str, object] | None = None,
) -> list[Evidence]:
    metadata = sender_metadata or {}
    is_job_offer = bool(_JOB_TERMS.search(text))
    if not is_job_offer:
        return []

    evidence: list[Evidence] = []
    if first_contact and not saved_contact:
        evidence.append(
            Evidence(
                "Unsolicited job offer",
                "This is a work offer in the first message from an unsaved sender.",
            )
        )
    if _contains_high_daily_earnings(text):
        evidence.append(
            Evidence(
                "Unrealistic earnings",
                "The message advertises at least $200 per day; that claim is not verified.",
            )
        )
    if _UPFRONT_PAYMENT.search(text):
        evidence.append(
            Evidence(
                "Upfront payment request",
                "The message asks for a payment to obtain or begin the job.",
            )
        )
    if not _ROLE_OR_DUTY_TERMS.search(text):
        evidence.append(
            Evidence(
                "Vague job details",
                "No role or duty terms recognized by this prototype's limited word list were found.",
            )
        )
    if _URGENCY.search(text):
        evidence.append(
            Evidence(
                "Urgency / pressure",
                "The message asks for a quick response or sets a short deadline.",
            )
        )

    employer_verified = metadata.get("employer_verified") is True
    employer_name = metadata.get("employer_name")
    name_appears_in_message = bool(_EMPLOYER_NAME.search(text))
    if not employer_verified:
        if employer_name:
            explanation = (
                f"The sender lists {employer_name} as the employer, but this demo "
                "has not independently verified that identity."
            )
        elif name_appears_in_message:
            explanation = (
                "An employer name appears in the message, but this demo has not "
                "independently verified that identity."
            )
        else:
            explanation = (
                "No employer name appears in the message or sender metadata; "
                "this demo cannot independently verify the sender."
            )
        evidence.append(Evidence("Unverified employer identity", explanation))

    return evidence
