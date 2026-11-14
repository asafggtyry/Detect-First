from detect_first.evidence import explain_message


def test_harmless_first_message_has_no_job_evidence() -> None:
    assert explain_message(
        "Hi, we met yesterday.",
        first_contact=True,
        saved_contact=False,
    ) == []


def test_job_offer_reasons_are_tied_to_observed_patterns() -> None:
    message = (
        "Hello! We are hiring students for remote work. Deposit $60 in the next "
        "24 hours to secure your position and start earning up to $300 per day. "
        "Reply now for onboarding details."
    )
    evidence = explain_message(
        message,
        first_contact=True,
        saved_contact=False,
        sender_metadata={"employer_verified": None},
    )
    categories = {item.category for item in evidence}
    assert categories == {
        "Unsolicited job offer",
        "Upfront payment request",
        "Unrealistic earnings",
        "Vague job details",
        "Urgency / pressure",
        "Unverified employer identity",
    }
    assert "not independently verify" in evidence[-1].explanation


def test_saved_contact_does_not_get_unsolicited_reason() -> None:
    evidence = explain_message(
        "We are hiring for a data entry position.",
        first_contact=True,
        saved_contact=True,
        sender_metadata={"employer_verified": True},
    )
    categories = {item.category for item in evidence}
    assert "Unsolicited job offer" not in categories
    assert "Unverified employer identity" not in categories
