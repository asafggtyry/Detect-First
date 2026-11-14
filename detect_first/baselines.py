from __future__ import annotations

import re


_SCAM_CUES = re.compile(
    r"\b(?:"
    r"upfront fee|registration fee|application fee|pay to apply|"
    r"deposit|wire transfer|gift cards?|cashier'?s check|"
    r"bank login|forward (?:the )?payments?|reship|"
    r"money mule|send back the (?:extra|remaining) amount"
    r")\b",
    re.IGNORECASE,
)


def always_legitimate(text: str) -> int:
    del text
    return 0


def keyword_scam_baseline(text: str) -> int:
    return int(bool(_SCAM_CUES.search(text)))
