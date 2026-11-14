from detect_first.server import create_app


def receive(client, seed=None, scenario_label=None):
    payload = {}
    if seed is not None:
        payload["seed"] = seed
    if scenario_label is not None:
        payload["scenario_label"] = scenario_label
    response = client.post("/api/demo/receive", json=payload)
    assert response.status_code == 200
    return response.json


def reset_with_seed(client, seed):
    response = client.post("/api/demo/reset", json={"seed": seed})
    assert response.status_code == 200
    assert response.json == {"reset": True, "seed": seed}


def seed_for_label(client, label, contains=None):
    for seed in range(100):
        reset_with_seed(client, seed)
        record = receive(client)["conversation"]
        if record["scenario_label"] == label and (
            contains is None or contains in record["messages"][0]["text"]
        ):
            return seed
    raise AssertionError(f"No seed produced scenario {label!r}.")


def test_synthetic_fixture_catalog_has_ten_examples_per_scenario():
    from collections import Counter

    from detect_first.simulation_fixtures import SCENARIO_LABELS, SIMULATION_FIXTURES

    counts = Counter(item.scenario_label for item in SIMULATION_FIXTURES)
    assert all(counts[label] >= 10 for label in SCENARIO_LABELS)
    assert all(item.message and item.sender_name for item in SIMULATION_FIXTURES)


def test_random_messages_vary_and_every_scenario_is_reachable():
    client = create_app(classifier=lambda _: False).test_client()
    generated = [receive(client, 704).get("conversation") for _ in range(12)]
    assert len({item["messages"][-1]["text"] for item in generated}) > 1
    unknown_ids = [item["id"] for item in generated if not item["saved_contact"]]
    assert len(unknown_ids) == len(set(unknown_ids))

    labels = set()
    for seed in range(100):
        reset_with_seed(client, seed)
        labels.add(receive(client)["conversation"]["scenario_label"])
    assert labels == {
        "family_friend",
        "normal_stranger",
        "potential_fraudulent_recruiter",
    }


def test_seeded_runs_reproduce_scenarios_and_messages_with_unique_ids():
    app = create_app(classifier=lambda _: False)
    first = app.test_client()
    second = app.test_client()

    first_run = [receive(first, 1234) if index == 0 else receive(first) for index in range(8)]
    second_run = [receive(second, 1234) if index == 0 else receive(second) for index in range(8)]
    for left, right in zip(first_run, second_run):
        assert left["conversation"]["scenario_label"] == right["conversation"]["scenario_label"]
        assert left["conversation"]["messages"] == right["conversation"]["messages"]
    first_ids = [item["conversation"]["id"] for item in first_run
                 if not item["conversation"]["saved_contact"]]
    second_ids = [item["conversation"]["id"] for item in second_run
                  if not item["conversation"]["saved_contact"]]
    assert len(first_ids) == len(set(first_ids))
    assert len(second_ids) == len(set(second_ids))
    assert set(first_ids).isdisjoint(second_ids)


def test_saved_contacts_bypass_scanning_and_reopening_does_not_rescan():
    calls = []
    client = create_app(classifier=lambda text: calls.append(text) or False).test_client()
    family_seed = seed_for_label(client, "family_friend")
    reset_with_seed(client, family_seed)
    calls.clear()
    family = receive(client)["conversation"]
    assert family["saved_contact"]
    assert family["analysis"]["scanned"] is False
    assert calls == []

    stranger_seed = seed_for_label(client, "normal_stranger")
    reset_with_seed(client, stranger_seed)
    calls.clear()
    stranger = receive(client)["conversation"]
    assert not stranger["saved_contact"]
    assert stranger["analysis"]["scanned"] is True
    assert len(calls) == 1
    assert client.get("/api/demo/history").json["conversations"][0] == stranger
    assert client.get("/api/demo/history").json["conversations"][0] == stranger
    later = client.post("/api/scan", json={
        "message": "A later message from this sender.",
        "sender": stranger["id"],
        "is_saved_contact": False,
        "is_first_message": False,
    })
    assert later.json["skipped_reason"] == "not_first_message"
    assert len(calls) == 1


def test_truth_label_does_not_force_live_prediction_or_warning():
    calls = []
    client = create_app(classifier=lambda text: calls.append(text) or False).test_client()
    recruiter_seed = seed_for_label(
        client, "potential_fraudulent_recruiter", "Northstar Talent"
    )
    reset_with_seed(client, recruiter_seed)
    calls.clear()
    result = receive(client)["conversation"]
    assert result["scenario_label"] == "potential_fraudulent_recruiter"
    assert result["analysis"]["model_flagged"] is False
    assert result["analysis"]["is_scam"] is False
    assert result["analysis"]["scanned"] is True
    assert calls == [result["messages"][0]["text"]]
    assert client.get("/api/demo/history").json["simulation_fixture_check"][
        "fraudulent_fixtures_missed"
    ] == 1

    selected = receive(client, scenario_label="family_friend")["conversation"]
    assert selected["scenario_label"] == "family_friend"
    assert selected["analysis"]["scanned"] is False
    assert client.post("/api/demo/receive", json={"scenario_label": "fraudulent"}).status_code == 400


def test_repeated_senders_keep_one_conversation_and_only_one_first_scan():
    calls = []
    client = create_app(classifier=lambda text: calls.append(text) or False).test_client()

    recruiter_messages = [
        receive(client, scenario_label="potential_fraudulent_recruiter")["conversation"]
        for _ in range(11)
    ]
    by_sender = {}
    for conversation in recruiter_messages:
        prior = by_sender.setdefault(conversation["sender"], conversation["id"])
        assert conversation["id"] == prior

    assert len(set(item["id"] for item in recruiter_messages)) == 10
    assert len(calls) == 10
    history = client.get("/api/demo/history").json
    repeated = next(item for item in history["conversations"] if len(item["messages"]) == 2)
    assert repeated["analysis"]["scanned"] is True
    assert len(repeated["messages"]) == 2

    family = [
        receive(client, scenario_label="family_friend")["conversation"]
        for _ in range(20)
    ]
    mom_records = [item for item in family if item["sender"] == "mom"]
    assert len(mom_records) == 2
    assert {item["id"] for item in mom_records} == {"mom"}
    assert all(item["analysis"]["scanned"] is False for item in family)
    assert len(calls) == 10


def test_scenario_check_reports_fixture_misses_and_false_positives_without_state():
    calls = []
    app = create_app(classifier=lambda text: calls.append(text) or False)
    client = app.test_client()
    result = client.get("/api/demo/check")

    assert result.status_code == 200
    data = result.json
    assert data["scope"] == "Synthetic demo fixtures only; not real-world accuracy."
    assert data["scenarios"]["family_friend"] == {
        "fixtures": 10,
        "scanned": 0,
        "model_flagged": 0,
        "warning_flagged": 0,
    }
    assert data["scenarios"]["normal_stranger"]["fixtures"] == 10
    assert data["scenarios"]["potential_fraudulent_recruiter"]["fixtures"] == 10
    assert data["fraudulent_fixtures_missed"] == (
        10 - data["scenarios"]["potential_fraudulent_recruiter"]["warning_flagged"]
    )
    assert data["fraudulent_fixtures_model_missed"] == 10
    assert data["synthetic_false_positive_warnings"] == 0
    assert len(calls) == 20
    assert all(isinstance(text, str) for text in calls)
    assert app.extensions["scan_service"].sessions == {}
    assert app.extensions["demo_simulation"].sessions == {}


def test_history_decisions_reset_and_api_errors():
    client = create_app(classifier=lambda _: False).test_client()
    assert client.get("/api/demo/history").json["conversations"] == []
    assert client.get("/api/demo/history").json["decisions"] == {}
    assert client.post("/api/demo/receive", data="{bad", content_type="application/json").status_code == 400
    assert client.post("/api/demo/receive", json={"seed": True}).status_code == 400
    assert client.post("/api/demo/receive", json={"seed": " "}).status_code == 400
    assert create_app(classifier=lambda _: False).test_client().post(
        "/api/demo/receive"
    ).status_code == 200

    record = receive(client, 98)["conversation"]
    assert client.post("/api/demo/receive", json={"seed": 99}).status_code == 409
    assert client.post(
        f"/api/demo/conversations/{record['id']}/decision",
        json={"decision": "block"},
    ).json["conversation"]["decision"] == "blocked"
    assert client.post(
        f"/api/demo/conversations/{record['id']}/decision",
        json={"decision": "accept"},
    ).json["conversation"]["decision"] == "accepted"
    assert client.get("/api/demo/history").json["decisions"][record["id"]] == "accepted"
    assert client.post(
        "/api/demo/conversations/missing/decision", json={"decision": "block"}
    ).status_code == 404
    assert client.post(
        f"/api/demo/conversations/{record['id']}/decision",
        json={"decision": "ignore"},
    ).status_code == 400
    assert client.post(
        f"/api/demo/conversations/{record['id']}/decision",
        json={"decision": []},
    ).status_code == 400

    assert client.post("/api/reset").json == {"reset": True}
    assert client.get("/api/demo/history").json["conversations"] == []
    assert client.get("/api/demo/history").json["decisions"] == {}
    assert client.post("/api/demo/reset", json={"unexpected": 1}).status_code == 400


def test_classifier_error_does_not_add_a_generated_conversation():
    calls = []

    def classifier(text):
        calls.append(text)
        if len(calls) == 1:
            raise RuntimeError("temporary failure")
        return False

    seed_client = create_app(classifier=lambda _: False).test_client()
    seed = seed_for_label(seed_client, "normal_stranger")
    client = create_app(classifier=classifier).test_client()
    failed = client.post("/api/demo/receive", json={"seed": seed})
    assert failed.status_code == 503
    assert "is_scam" not in failed.json
    assert client.get("/api/demo/history").json["conversations"] == []

    recovered = receive(client, seed)["conversation"]
    assert recovered["analysis"]["scanned"] is True
    assert len(calls) == 2
