from __future__ import annotations

from datetime import datetime, UTC
from email.parser import Parser
from pathlib import Path
import json
import re
import uuid


DEFAULT_SENDERS = [
    "Seaman",
    "SeaMail",
    "System",
    "Hiroko",
    "Research Team",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def safe_stem(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return cleaned[:40] or "message"


class MailboxStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.mail_in_dir = self.base_dir / "mail_in"
        self.mail_out_dir = self.base_dir / "mail_out"
        self.state_path = self.base_dir / "mailbox_state.json"

        self.mail_in_dir.mkdir(parents=True, exist_ok=True)
        self.mail_out_dir.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> dict:
        return {"messages": [], "senders": list(DEFAULT_SENDERS)}

    def _load_state(self) -> dict:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        else:
            data = self._default_state()

        data.setdefault("messages", [])
        data.setdefault("senders", list(DEFAULT_SENDERS))
        self._bootstrap_presets(data)
        self._write_state(data)
        return data

    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _bootstrap_presets(self, state: dict) -> None:
        known_filenames = {message["filename"] for message in state["messages"]}
        for file_path in sorted(self.mail_in_dir.glob("*.txt")):
            if file_path.name in known_filenames:
                continue

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            timestamp = utc_now()
            state["messages"].append(
                {
                    "id": uuid.uuid4().hex,
                    "filename": file_path.name,
                    "sender": "",
                    "subject": file_path.stem.replace("_", " ").title(),
                    "description": "Imported preset from the original mail_in folder.",
                    "body_original": content,
                    "body_translated": "",
                    "delivery_text": content,
                    "deliver_translated": False,
                    "preset": True,
                    "enabled": True,
                    "pulled_once": False,
                    "pulled_at": None,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
            )

    def _render_delivery_text(self, message: dict) -> str:
        if message.get("delivery_text"):
            return message["delivery_text"]

        body = message.get("body_translated") if message.get("deliver_translated") and message.get("body_translated") else message.get("body_original", "")
        sender = message.get("sender", "").strip()
        subject = message.get("subject", "").strip()

        if not sender and not subject:
            return body

        headers = []
        if sender:
            headers.append(f"From: {sender}")
        if subject:
            headers.append(f"Subject: {subject}")
        return "\n".join([*headers, "", body]).strip()

    def _sync_mail_in(self, state: dict) -> None:
        expected = {}
        for message in state["messages"]:
            if message.get("enabled"):
                delivery_text = self._render_delivery_text(message)
                message["delivery_text"] = delivery_text
                expected[message["filename"]] = delivery_text

        for file_path in self.mail_in_dir.glob("*.txt"):
            if file_path.name not in expected:
                file_path.unlink(missing_ok=True)

        for filename, content in expected.items():
            target = self.mail_in_dir / filename
            target.write_text(content, encoding="utf-8")

    def list_inbox_messages(self) -> dict:
        state = self._load_state()
        self._sync_mail_in(state)
        messages = sorted(state["messages"], key=lambda item: item.get("created_at", ""), reverse=True)
        summary = {
            "total": len(messages),
            "enabled": sum(1 for item in messages if item.get("enabled")),
            "pulled": sum(1 for item in messages if item.get("pulled_once")),
        }
        return {"messages": messages, "senders": state["senders"], "summary": summary}

    def create_message(self, payload: dict) -> dict:
        state = self._load_state()
        timestamp = utc_now()

        sender = payload.get("sender", "").strip()
        subject = payload.get("subject", "").strip()
        description = payload.get("description", "").strip()
        body_original = payload.get("body_original", "").strip()
        body_translated = payload.get("body_translated", "").strip()
        deliver_translated = bool(payload.get("deliver_translated")) and bool(body_translated)
        delivery_text = payload.get("delivery_text", "").strip()

        if not body_original and not body_translated and not delivery_text:
            raise ValueError("Message body cannot be empty")

        base_name = safe_stem(subject or sender or "mail")
        filename = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        message = {
            "id": uuid.uuid4().hex,
            "filename": filename,
            "sender": sender,
            "subject": subject,
            "description": description,
            "body_original": body_original,
            "body_translated": body_translated,
            "delivery_text": delivery_text,
            "deliver_translated": deliver_translated,
            "preset": bool(payload.get("preset")),
            "enabled": bool(payload.get("enabled", True)),
            "pulled_once": False,
            "pulled_at": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        if sender and sender not in state["senders"]:
            state["senders"].append(sender)

        state["messages"].append(message)
        self._sync_mail_in(state)
        self._write_state(state)
        return message

    def set_message_enabled(self, message_id: str, enabled: bool, *, reset_pulled: bool = False) -> dict | None:
        state = self._load_state()
        for message in state["messages"]:
            if message["id"] != message_id:
                continue

            message["enabled"] = enabled
            if reset_pulled:
                message["pulled_once"] = False
                message["pulled_at"] = None
            message["updated_at"] = utc_now()
            self._sync_mail_in(state)
            self._write_state(state)
            return message
        return None

    def mark_message_pulled_by_filename(self, filename: str) -> dict | None:
        state = self._load_state()
        for message in state["messages"]:
            if message["filename"] != filename:
                continue

            message["enabled"] = False
            message["pulled_once"] = True
            message["pulled_at"] = utc_now()
            message["updated_at"] = utc_now()
            self._sync_mail_in(state)
            self._write_state(state)
            return message
        return None

    def list_outbox_messages(self) -> list[dict]:
        files = sorted(
            [path for path in self.mail_out_dir.rglob("*.txt") if path.is_file()],
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

        messages = []
        for file_path in files:
            raw = file_path.read_text(encoding="utf-8", errors="ignore")
            parsed = Parser().parsestr(raw)
            headers = {key: value for key, value in parsed.items()}
            body = parsed.get_payload() if headers else raw

            messages.append(
                {
                    "filename": file_path.name,
                    "relative_path": str(file_path.relative_to(self.base_dir)).replace("\\", "/"),
                    "modified_at": datetime.fromtimestamp(file_path.stat().st_mtime, UTC).isoformat(),
                    "sender": headers.get("From", ""),
                    "subject": headers.get("Subject", file_path.stem),
                    "headers": headers,
                    "body": body.strip(),
                    "raw": raw,
                }
            )
        return messages
