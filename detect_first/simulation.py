from __future__ import annotations

import copy
import random
import re
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

from detect_first.simulation_fixtures import SCENARIO_LABELS, SIMULATION_FIXTURES, MessageFixture


class SeedConflict(ValueError):
    """A session cannot change its deterministic sequence after generation starts."""


@dataclass
class SimulationSession:
    seed: int | str | None
    rng: random.Random
    conversations: dict[str, dict] = field(default_factory=dict)
    used_fixtures: dict[str, set[int]] = field(
        default_factory=lambda: {label: set() for label in SCENARIO_LABELS}
    )
    generated: int = 0


class SimulationService:
    """Session-scoped synthetic incoming messages; predictions use only message text."""

    def __init__(self) -> None:
        self.sessions: dict[str, SimulationSession] = {}
        self.lock = Lock()

    def reset(self, session_id: str, seed: int | str | None = None) -> None:
        with self.lock:
            self.sessions.pop(session_id, None)
            if seed is not None:
                self.sessions[session_id] = SimulationSession(seed, random.Random(seed))

    def receive(
        self,
        session_id: str,
        scan: Callable[[dict], dict],
        seed: int | str | None = None,
    ) -> dict:
        with self.lock:
            state = self.sessions.get(session_id)
            if state is None:
                state = SimulationSession(seed, random.Random(seed))
                self.sessions[session_id] = state
            elif seed is not None and seed != state.seed:
                if state.generated:
                    raise SeedConflict(
                        "A seed can only be changed before the first generated message. Reset the demo first."
                    )
                state.seed = seed
                state.rng.seed(seed)

            rng_state = state.rng.getstate()
            used_before = {key: set(value) for key, value in state.used_fixtures.items()}
            selected_label = state.rng.choice(SCENARIO_LABELS)
            eligible = [
                (index, fixture)
                for index, fixture in enumerate(SIMULATION_FIXTURES)
                if fixture.scenario_label == selected_label
                and index not in state.used_fixtures[selected_label]
            ]
            if not eligible:
                state.used_fixtures[selected_label].clear()
                eligible = [
                    (index, fixture)
                    for index, fixture in enumerate(SIMULATION_FIXTURES)
                    if fixture.scenario_label == selected_label
                ]
            fixture_index, fixture = state.rng.choice(eligible)
            state.used_fixtures[selected_label].add(fixture_index)

            conversation_id = self._conversation_id(fixture)
            try:
                scan_result = scan({
                    "sender": conversation_id,
                    "message": fixture.message,
                    "is_saved_contact": fixture.saved_contact,
                    "is_first_message": True,
                })
            except Exception:
                state.rng.setstate(rng_state)
                state.used_fixtures = used_before
                raise

            existing = state.conversations.get(conversation_id)
            if existing is None:
                conversation = {
                    "id": conversation_id,
                    "sender_name": fixture.sender_name,
                    "sender": fixture.sender,
                    "saved_contact": fixture.saved_contact,
                    "scenario_label": fixture.scenario_label,
                    "synthetic": True,
                    "messages": [],
                    "analysis": scan_result,
                    "decision": None,
                }
                state.conversations[conversation_id] = conversation
            else:
                conversation = existing
            conversation["messages"].append({
                "direction": "incoming",
                "text": fixture.message,
                "synthetic": True,
            })
            state.generated += 1
            return {
                "conversation": copy.deepcopy(conversation),
                "simulation_fixture_check": self._fixture_check(state),
            }

    def history(self, session_id: str) -> dict:
        with self.lock:
            state = self.sessions.get(session_id)
            if state is None:
                return {"conversations": [], "simulation_fixture_check": self._empty_check()}
            return {
                "conversations": copy.deepcopy(list(state.conversations.values())),
                "simulation_fixture_check": self._fixture_check(state),
            }

    def decide(self, session_id: str, conversation_id: str, decision: str) -> dict | None:
        with self.lock:
            state = self.sessions.get(session_id)
            if state is None or conversation_id not in state.conversations:
                return None
            state.conversations[conversation_id]["decision"] = decision
            return copy.deepcopy(state.conversations[conversation_id])

    @staticmethod
    def _conversation_id(fixture: MessageFixture) -> str:
        if fixture.saved_contact:
            return "saved-" + re.sub(r"[^a-z0-9]+", "-", fixture.sender.lower()).strip("-")
        return str(uuid.uuid4())

    @staticmethod
    def _fixture_check(state: SimulationSession) -> dict:
        fraud = [
            item for item in state.conversations.values()
            if item["scenario_label"] == "potential_fraudulent_recruiter"
        ]
        normal = [
            item for item in state.conversations.values()
            if item["scenario_label"] == "normal_stranger"
        ]
        flagged = sum(item["analysis"]["is_scam"] is True for item in fraud)
        return {
            "fraudulent_fixtures_generated": len(fraud),
            "fraudulent_fixtures_flagged": flagged,
            "fraudulent_fixtures_missed": len(fraud) - flagged,
            "fraudulent_fixtures_model_flagged": sum(
                item["analysis"]["model_flagged"] is True for item in fraud
            ),
            "normal_stranger_fixtures_generated": len(normal),
            "normal_stranger_fixtures_flagged": sum(
                item["analysis"]["is_scam"] is True for item in normal
            ),
            "normal_stranger_fixtures_model_flagged": sum(
                item["analysis"]["model_flagged"] is True for item in normal
            ),
            "scope": "Synthetic demo fixtures only; not real-world accuracy.",
        }

    @staticmethod
    def _empty_check() -> dict:
        return {
            "fraudulent_fixtures_generated": 0,
            "fraudulent_fixtures_flagged": 0,
            "fraudulent_fixtures_missed": 0,
            "fraudulent_fixtures_model_flagged": 0,
            "normal_stranger_fixtures_generated": 0,
            "normal_stranger_fixtures_flagged": 0,
            "normal_stranger_fixtures_model_flagged": 0,
            "scope": "Synthetic demo fixtures only; not real-world accuracy.",
        }
