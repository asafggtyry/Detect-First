"""New backend regression texts; no final-benchmark or demo examples."""
import copy
import json
from pathlib import Path

import pytest

from detect_first.experimental_policy import analyze_rules, combine, POLICIES
from detect_first.server import ScanService
from scripts import experiment_false_positives as experiment


@pytest.mark.parametrize("text", [
    "We are hiring a potter. Interviews start today and the rate is $260 a day.",
    "The company will pay for equipment before the new employee arrives for the job.",
    "Please do not pay a deposit before your interview for this position.",
    "This job includes a gift card reward, which our office purchases for staff.",
    "The employment workshop describes a fraud: deposit a check and forward the money.",
    "For the accounting job, use company systems to transfer funds; personal accounts are prohibited.",
    "The dispatch role receives parcels at a warehouse and forwards them on trucks.",
    "Following your completed interview and accepted offer, enter payroll details in the established HR portal.",
    "Never share your banking password for payroll. We are hiring through a public listing.",
    "Please reply today if interested in our job vacancy. We can explain the duties during a call.",
])
@pytest.mark.parametrize("policy", POLICIES)
def test_legitimate_recruiting_context_is_not_enough(text, policy):
    assert analyze_rules(text, policy)["rule_flagged"] is False


@pytest.mark.parametrize("text,category", [
    ("For this job, pay a registration fee before your application is approved.", "applicant_payment"),
    ("Our hiring task requires you to buy gift cards and email their codes.", "gift_card_transfer"),
    ("For the job, cash a cheque and wire the remainder to our agent.", "check_redirection"),
    ("For this work, receive customer money in your personal account and forward the funds.", "personal_account_transfer"),
    ("Your job is to receive packages at home and reship them to strangers.", "home_reshipping"),
    ("To activate payroll, share your online banking password with the recruiter.", "authentication_secret"),
])
@pytest.mark.parametrize("policy", POLICIES)
def test_strong_combinations_and_exact_spans(text, category, policy):
    result = analyze_rules(text, policy)
    assert result["rule_flagged"] is True
    assert category in {s["category"] for s in result["signals"]}
    for signal in result["signals"]:
        assert text[signal["start"]:signal["end"]] == signal["excerpt"]
        assert signal["source"] == "experimental_evidence_rule"


def test_sensitive_extension_is_explicit_and_not_authentication_explanation():
    text = "Before your job interview, send your routing number in a reply to the recruiter."
    assert not analyze_rules(text, "strong_actions")["rule_flagged"]
    signals = analyze_rules(text, "strong_actions_sensitive")["signals"]
    assert [s["category"] for s in signals] == ["early_sensitive_information"]


def test_unrelated_negation_does_not_suppress_a_later_demand():
    text = "No problem with your job application. Pay the equipment fee before starting."
    assert analyze_rules(text)["rule_flagged"]


def test_newline_terminated_request_keeps_its_original_offsets():
    text = "For this job pay a deposit before hiring\nWe will discuss dates later."
    result = analyze_rules(text)
    assert result["rule_flagged"]
    for signal in result["signals"]:
        assert text[signal["start"]:signal["end"]] == signal["excerpt"]


def test_production_rules_are_not_replaced():
    text = "We are hiring a botanist for the spring season."
    actual = ScanService(lambda _: False).analyze(text)
    assert actual["evidence_flagged"] is True and actual["is_scam"] is True
    assert not analyze_rules(text)["rule_flagged"]
    experiment.verify_protected()


def test_model_and_rules_stay_separate():
    assert combine(True, False) is True
    assert combine(False, True) is True
    assert combine(False, False) is False
    with pytest.raises(ValueError):
        combine(None, True)
    with pytest.raises(ValueError):
        analyze_rules("A job message", "unknown")


def test_labels_and_scenario_metadata_never_enter_predictor(monkeypatch):
    observed = []
    def analyzer(text):
        assert isinstance(text, str)
        observed.append(text)
        return {"model_flagged": False, "evidence_flagged": True, "is_scam": True, "reasons": []}
    rows = [{"id": "poison-scam", "text": "A hiring invitation", "label": 1, "family": "fraud"}]
    first = experiment.score_rows(rows, POLICIES, analyzer)
    altered = [dict(rows[0], id="poison-legitimate", label=0, family="legitimate")]
    second = experiment.score_rows(altered, POLICIES, analyzer)
    assert observed == [rows[0]["text"], rows[0]["text"]]
    assert first["records"][0]["predictions"] == second["records"][0]["predictions"]
    assert first["records"][0]["reference_label"] != second["records"][0]["reference_label"]


def test_selection_enforces_guardrails_before_f1_and_reports_diagnostic_fallback():
    metrics = {"original_combined": {"f1": .60, "false_positives": 12, "false_negatives": 8}}
    metrics["strong_actions_combined"] = {"f1": .72, "false_positives": 1, "false_negatives": 8, "false_positive_rate": .025}
    metrics["strong_actions_sensitive_combined"] = {"f1": .85, "false_positives": 4, "false_negatives": 2, "false_positive_rate": .1}
    selected = experiment.select_candidate(metrics)
    assert selected["selected_policy"] == "strong_actions"
    assert selected["passes_development_gate"]
    changed = copy.deepcopy(metrics)
    changed["strong_actions_combined"]["false_negatives"] = 9
    selected = experiment.select_candidate(changed)
    assert selected["selected_policy"] == "strong_actions_sensitive"
    assert not selected["passes_development_gate"]


def test_final_run_marker_and_outputs_cannot_be_overwritten(tmp_path):
    experiment.claim_final_run(tmp_path, {"selected": "frozen"})
    with pytest.raises(FileExistsError):
        experiment.claim_final_run(tmp_path, {"selected": "different"})
    assert json.loads((tmp_path / "final_run_started.json").read_text()) == {"selected": "frozen"}
    other = tmp_path / "completed"
    other.mkdir()
    (other / "final.json").write_text("{}")
    with pytest.raises(FileExistsError):
        experiment.claim_final_run(other, {})


def test_final_rejects_changed_frozen_inputs_before_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "OUT", tmp_path)
    monkeypatch.setattr(experiment, "verify_protected", lambda: None)
    monkeypatch.setattr(experiment, "git", lambda *args: "")
    monkeypatch.setattr(experiment, "frozen_inputs", lambda: {"code": "changed"})
    monkeypatch.setattr(experiment, "load_pipeline", lambda _: pytest.fail("Must not predict"))
    (tmp_path / "selection.json").write_text(json.dumps({"inputs": {"code": "frozen"}}))
    with pytest.raises(ValueError, match="inputs changed"):
        experiment.final()
    assert not (tmp_path / "final_run_started.json").exists()
