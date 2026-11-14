from detect_first.state import ConversationStore, create_demo_store


def test_saved_contact_is_never_sent_to_classifier() -> None:
    scanned: list[str] = []
    store = create_demo_store(lambda text: scanned.append(text) or False)
    assert scanned == [
        "Hi, we met yesterday.",
        store.get("732-882-1944").messages[0].text,
    ]
    assert store.get("mom").scanned
    assert store.get("mom").scan_count == 0
    assert len(scanned) == 2
    assert store.get("124-5135-2355").scan_count == 1
    assert store.get("732-882-1944").scan_count == 1


def test_first_message_scanned_once_and_later_message_is_not() -> None:
    scanned: list[str] = []
    store = create_demo_store(lambda text: scanned.append(text) or False)
    initial_count = len(scanned)
    store.add_incoming("124-5135-2355", "A later message from this sender.")
    assert len(scanned) == initial_count
    assert store.get("124-5135-2355").scan_count == 1


def test_block_and_accept_update_state() -> None:
    blocked_store = create_demo_store(lambda _text: False)
    suspicious = blocked_store.get("732-882-1944")
    assert suspicious.should_warn

    blocked_store.block(suspicious.sender_id)
    assert suspicious.blocked
    assert not suspicious.should_warn

    accepted_store = create_demo_store(lambda _text: False)
    accepted = accepted_store.get("732-882-1944")
    assert accepted.should_warn
    accepted_store.accept_anyway(accepted.sender_id)
    assert accepted.accepted
    assert not accepted.should_warn


def test_reset_recreates_initial_demo_state_and_scans_first_messages() -> None:
    scan_calls: list[str] = []
    first_run = create_demo_store(lambda text: scan_calls.append(text) or True)
    first_run.block("732-882-1944")
    first_run.accept_anyway("124-5135-2355")

    reset_store = create_demo_store(lambda text: scan_calls.append(text) or True)
    assert not reset_store.get("732-882-1944").blocked
    assert not reset_store.get("124-5135-2355").accepted
    assert reset_store.get("124-5135-2355").scan_count == 1
    assert reset_store.get("732-882-1944").scan_count == 1
    assert len(scan_calls) == 4


def test_test_conversation_is_scanned_once_then_not_rescanned() -> None:
    scanned: list[str] = []
    store = ConversationStore(lambda text: scanned.append(text) or False, [])
    conversation = store.add_test_conversation("999-000-0000", "First test message")
    store.add_incoming("999-000-0000", "Second test message")
    assert scanned == ["First test message"]
    assert conversation.scan_count == 1
