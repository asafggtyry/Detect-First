"""Offline policy experiment only. Never imported by the production server.

Signals describe lexical rule observations, never ML explanations or proof of
fraud. No labels, IDs, sender categories or fixture metadata enter this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

POLICIES = ("strong_actions", "strong_actions_sensitive")


def rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


RECRUITMENT = rx(r"\b(?:job|work|position|role|employ\w*|hiring|recruit\w*|vacancy|"
                 r"payroll|salary|wages|assignment|onboarding|interview|commission)\b")
EDUCATION = rx(r"\b(?:workshop|lesson|training slide|warning example|fraud.awareness|"
              r"report messages|policy says|scam instruction)\b")
NEGATED_PREFIX = rx(r"\b(?:never|do not|don't|must not|won't|will not|not required to|"
                   r"no need to|do not need to)\b[^.!?;]{0,70}$")
EMPLOYER_PAYS = rx(r"\b(?:we|the company|the employer|our office)\s+(?:will\s+)?$")
PAYMENT = rx(r"\b(?:pay|send|transfer|purchase|buy)\b.{0,65}?"
             r"\b(?:fee|deposit|charge|equipment|kit|certification|activation)\b")
PREREQUISITE = rx(r"\b(?:before|must|required|mandatory|to (?:start|secure|unlock|activate)|"
                  r"once you|in advance|upfront)\b")
GIFT_PURCHASE = rx(r"\b(?:buy|purchase|send)\b.{0,45}?\bgift cards?\b")
CODE_TRANSFER = rx(r"\b(?:send|email|reply|text|share|provide)\b.{0,60}?"
                  r"\b(?:codes?|numbers?|PIN|photo)\b")
CHECK_DEPOSIT = rx(r"\b(?:deposit|cash|depositing)\b.{0,40}?\b(?:check|cheque)\b")
FORWARD_FUNDS = rx(r"\b(?:send|wire|transfer|forward)\b.{0,55}?"
                  r"\b(?:money|funds|balance|remainder|rest|proceeds|onward|vendor|supplier)\b")
CHECK_PURCHASE = rx(r"\b(?:buy|buying|purchase)\b.{0,40}?\b(?:equipment|gift cards?)\b")
PERSONAL_ACCOUNT = rx(r"\b(?:your|personal|own)\s+(?:(?:own|personal|bank)\s+){0,2}account\b")
RECEIVE_FUNDS = rx(r"\b(?:receive|accept|collect)\b.{0,50}?"
                  r"\b(?:funds|money|payments|transfers)\b")
RECEIVE_PARCELS = rx(r"\b(?:receive|accept|collect)\b.{0,45}?\b(?:packages|parcels|electronics)\b")
HOME = rx(r"\b(?:at (?:your )?home|at your house|your apartment|your residence)\b")
RESHIP = rx(r"\b(?:reship|repackage|forward)\b")
REQUEST_SECRET = rx(r"\b(?:send|share|reply|text|provide)\b.{0,75}?"
                   r"\b(?:password|banking PIN|bank login|one.time code|verification code)\b")
SECRET_REQUEST_REVERSED = rx(r"\b(?:password|banking PIN|bank login|one.time code)\b.{0,60}?"
                           r"\b(?:text|send|share|reply)\b")
IDENTITY_REQUEST = rx(r"\b(?:send|share|reply|provide)\b.{0,75}?"
                     r"\b(?:social security number|passport number|driv(?:ing|er's) licen[sc]e|"
                     r"routing number|bank account|account details)\b")
EARLY_OR_CHANNEL = rx(r"\b(?:before|not been interviewed|interviews come later|"
                      r"reply|by (?:text|message)|in this chat|to book an interview)\b")


@dataclass(frozen=True)
class Signal:
    category: str
    start: int
    end: int
    excerpt: str
    explanation: str
    source: str = "experimental_evidence_rule"


def _active_matches(pattern: re.Pattern, sentence: str, *, payment: bool = False):
    for match in pattern.finditer(sentence):
        prefix = sentence[:match.start()]
        if NEGATED_PREFIX.search(prefix):
            continue
        if payment and EMPLOYER_PAYS.search(prefix):
            continue
        yield match


def analyze_rules(text: str, policy: str = "strong_actions_sensitive") -> dict:
    """Text-only rule predictions; no scoring/ground truth accepted or returned."""
    if policy not in POLICIES:
        raise ValueError("Unknown experimental policy")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Expected non-empty message text")
    signals: list[Signal] = []
    if RECRUITMENT.search(text):
        for sentence_match in re.finditer(r"[^.!?;\n]+(?:[.!?;\n]|$)", text):
            sentence = sentence_match.group()
            if EDUCATION.search(sentence):
                continue

            def active(pattern, payment=False):
                return next(_active_matches(pattern, sentence, payment=payment), None)

            def emit(category, explanation, *matches):
                begin = sentence_match.start() + min(m.start() for m in matches)
                end = sentence_match.start() + max(m.end() for m in matches)
                signals.append(Signal(category, begin, end, text[begin:end], explanation))

            payment = active(PAYMENT, payment=True)
            prerequisite = PREREQUISITE.search(sentence)
            if payment and prerequisite:
                emit("applicant_payment", "Payment/purchase wording is tied to a hiring prerequisite.",
                     payment, prerequisite)
            gift, code = active(GIFT_PURCHASE), active(CODE_TRANSFER)
            if gift and code:
                emit("gift_card_transfer", "Gift-card action is paired with transmission of codes or numbers.", gift, code)
            check = active(CHECK_DEPOSIT)
            forward = active(FORWARD_FUNDS)
            purchase = active(CHECK_PURCHASE)
            if check and (forward or purchase):
                emit("check_redirection", "Check deposit is paired with forwarding or spending its funds.",
                     check, forward or purchase)
            personal = PERSONAL_ACCOUNT.search(sentence)
            receive = active(RECEIVE_FUNDS)
            if personal and receive and forward:
                emit("personal_account_transfer", "Receiving and forwarding funds uses a personal account.",
                     personal, receive, forward)
            parcels, home, reship = active(RECEIVE_PARCELS), HOME.search(sentence), active(RESHIP)
            if parcels and home and reship:
                emit("home_reshipping", "Home parcel receipt is paired with repackaging or forwarding.", parcels, home, reship)
            secret = active(REQUEST_SECRET) or active(SECRET_REQUEST_REVERSED)
            if secret:
                emit("authentication_secret", "The message requests transmission of an authentication secret.", secret)
            identity, early = active(IDENTITY_REQUEST), EARLY_OR_CHANNEL.search(sentence)
            if policy == "strong_actions_sensitive" and identity and early:
                emit("early_sensitive_information", "A sensitive-data request uses an early-hiring or reply/chat context.",
                     identity, early)
    return {"rule_flagged": bool(signals), "signals": [asdict(signal) for signal in signals],
            "policy": policy}


def combine(model_flagged: bool, rule_flagged: bool) -> bool:
    if type(model_flagged) is not bool or type(rule_flagged) is not bool:
        raise ValueError("Model and rule predictions must remain separate Boolean values")
    return model_flagged or rule_flagged
