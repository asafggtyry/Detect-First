from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from detect_first.evidence import Evidence, explain_message


Classifier = Callable[[str], bool]


@dataclass
class Message:
    text: str
    direction: str
    time: str = "9:04 AM"
    synthetic: bool = False


@dataclass
class Conversation:
    sender_id: str
    name: str
    saved_contact: bool
    messages: list[Message]
    sender_metadata: dict[str, object] = field(default_factory=dict)
    scanned: bool = False
    scan_count: int = 0
    model_flagged: bool | None = None
    evidence: list[Evidence] = field(default_factory=list)
    blocked: bool = False
    accepted: bool = False
    synthetic: bool = False

    @property
    def preview(self) -> str:
        return self.messages[-1].text if self.messages else "No messages yet"

    @property
    def should_warn(self) -> bool:
        return bool(
            self.scanned
            and not self.blocked
            and not self.accepted
            and (
                self.model_flagged is True
                or len(self.evidence) >= 2
            )
        )


class ConversationStore:
    def __init__(
        self,
        classifier: Classifier,
        conversations: list[Conversation],
    ) -> None:
        self.classifier = classifier
        self.conversations = {item.sender_id: item for item in conversations}
        if len(self.conversations) != len(conversations):
            raise ValueError("Conversation sender IDs must be unique.")
        for conversation in self.conversations.values():
            first_incoming = next(
                (
                    message
                    for message in conversation.messages
                    if message.direction == "incoming"
                ),
                None,
            )
            if first_incoming is not None:
                self._scan_first_message(conversation, first_incoming.text)

    def _scan_first_message(self, conversation: Conversation, text: str) -> None:
        if conversation.saved_contact:
            conversation.scanned = True
            conversation.model_flagged = None
            return
        if conversation.scan_count:
            return

        conversation.model_flagged = bool(self.classifier(text))
        conversation.evidence = explain_message(
            text,
            first_contact=True,
            saved_contact=False,
            sender_metadata=conversation.sender_metadata,
        )
        conversation.scan_count += 1
        conversation.scanned = True

    def add_incoming(
        self, sender_id: str, text: str, *, synthetic: bool = False
    ) -> Conversation:
        if not text.strip():
            raise ValueError("Message text cannot be empty.")
        conversation = self.conversations[sender_id]
        conversation.messages.append(
            Message(
                text=text.strip(),
                direction="incoming",
                time=datetime.now().strftime("%I:%M %p").lstrip("0"),
                synthetic=synthetic,
            )
        )
        if not conversation.scanned:
            self._scan_first_message(conversation, text)
        return conversation

    def add_test_conversation(
        self, sender_id: str, text: str, *, synthetic: bool = True
    ) -> Conversation:
        normalized_id = sender_id.strip()
        if not normalized_id:
            raise ValueError("A sender ID is required.")
        if normalized_id in self.conversations:
            return self.add_incoming(
                normalized_id, text, synthetic=synthetic
            )
        conversation = Conversation(
            sender_id=normalized_id,
            name=normalized_id,
            saved_contact=False,
            messages=[
                Message(
                    text=text.strip(),
                    direction="incoming",
                    time=datetime.now().strftime("%I:%M %p").lstrip("0"),
                    synthetic=synthetic,
                )
            ],
            synthetic=synthetic,
        )
        self.conversations[normalized_id] = conversation
        self._scan_first_message(conversation, text)
        return conversation

    def send_outgoing(self, sender_id: str, text: str) -> None:
        if not text.strip():
            raise ValueError("Message text cannot be empty.")
        conversation = self.conversations[sender_id]
        conversation.messages.append(
            Message(
                text=text.strip(),
                direction="outgoing",
                time=datetime.now().strftime("%I:%M %p").lstrip("0"),
            )
        )

    def block(self, sender_id: str) -> None:
        self.conversations[sender_id].blocked = True

    def accept_anyway(self, sender_id: str) -> None:
        self.conversations[sender_id].accepted = True

    def get(self, sender_id: str) -> Conversation:
        return self.conversations[sender_id]


def create_demo_store(classifier: Classifier) -> ConversationStore:
    return ConversationStore(
        classifier,
        [
            Conversation(
                sender_id="mom",
                name="Mom",
                saved_contact=True,
                sender_metadata={"employer_verified": None},
                messages=[
                    Message(
                        "How are you?",
                        direction="incoming",
                        time="9:00 AM",
                    )
                ],
            ),
            Conversation(
                sender_id="124-5135-2355",
                name="124-5135-2355",
                saved_contact=False,
                sender_metadata={"employer_verified": None},
                messages=[
                    Message(
                        "Hi, we met yesterday.",
                        direction="incoming",
                        time="9:02 AM",
                    )
                ],
            ),
            Conversation(
                sender_id="732-882-1944",
                name="732-882-1944",
                saved_contact=False,
                sender_metadata={"employer_verified": None},
                messages=[
                    Message(
                        "Hello! We are hiring students for remote work. "
                        "Deposit $60 in the next 24 hours to secure your "
                        "position and start earning up to $300 per day. "
                        "Reply now for onboarding details.",
                        direction="incoming",
                        time="9:04 AM",
                    )
                ],
            ),
        ],
    )
