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
    by_category = {item.category: item for item in evidence}
    assert by_category["Unsolicited job offer"].snippet == "hiring"
    assert by_category["Upfront payment request"].snippet == "Deposit $60"
    assert by_category["Urgency / pressure"].snippet == "next 24 hours"
    assert by_category["Vague job details"].snippet is None


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


def test_spans_use_exact_unicode_input_offsets_and_are_deterministically_ordered() -> None:
    message = "🙂 Café! We are hiring. Deposit $60, then within 24 hours; deposit $60."
    evidence = explain_message(message, first_contact=True, saved_contact=False)
    spans = [item for item in evidence if item.start is not None]

    assert spans
    assert spans == sorted(spans, key=lambda item: (item.start, item.end, item.category))
    for item in spans:
        assert item.snippet == message[item.start:item.end]
    payment = next(item for item in spans if item.category == "Upfront payment request")
    assert payment.snippet == "Deposit $60"
    assert message.index(payment.snippet) == payment.start
    assert any(item.snippet == "within 24 hours" for item in spans)


def test_unanchored_context_reasons_do_not_create_highlights() -> None:
    message = "We are hiring."
    evidence = explain_message(message, first_contact=True, saved_contact=False)
    assert any(item.category == "Vague job details" and item.start is None for item in evidence)
    assert any(item.category == "Unverified employer identity" and item.end is None for item in evidence)
    assert all(
        item.start is None or item.snippet == message[item.start:item.end]
        for item in evidence
    )
