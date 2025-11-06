# telegram_notify.py  (English comments)
# pip install requests
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
import requests

class TelegramNotifier:
    """Telegram notifier with rate-limiting, dedupe-on-base-text, timestamp append, and skip counter."""
    def __init__(self, bot_token=None, chat_id=None, store_path="~/.telegram_notify_state.json"):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = int(chat_id or os.getenv("TELEGRAM_CHAT_ID", "0"))
        if not self.bot_token or not self.chat_id:
            raise ValueError("Missing bot token or chat_id")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.state_path = Path(store_path).expanduser()
        self.lock = threading.Lock()

        # Tunables
        self.min_interval = 10        # seconds between messages to same chat
        self.daily_cap = 10           # max messages per 24h
        self.dedupe_window = 3600     # seconds; don't resend identical *base* message within this window
        self.append_timestamp = True  # automatically add a timestamp to the sent message

        self._load_state()

    def _load_state(self):
        if self.state_path.exists():
            try:
                self.state = json.loads(self.state_path.read_text())
            except Exception:
                self.state = {}
        else:
            self.state = {}

        now = int(time.time())
        s = self.state.get(str(self.chat_id), {})
        # ensure keys exist
        s.setdefault("last_sent_ts", 0)
        s.setdefault("daily_count", 0)
        s.setdefault("last_base_message", "")
        s.setdefault("daily_reset_ts", now + 24*3600)
        s.setdefault("skipped_since_last_send", 0)

        if s.get("daily_reset_ts", 0) < now:
            # simple 24h roll-over; good enough for a domestic notifier
            s["daily_count"] = 0
            s["daily_reset_ts"] = now + 24*3600

        self.state[str(self.chat_id)] = s
        self._save_state()

    def _save_state(self):
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.state))
        except Exception:
            # never crash the notifier for persistence issues
            pass

    def _can_send(self, base_text: str):
        """Check rate limits and dedupe on the *base* text (without timestamp). Return (ok, reason)."""
        now = int(time.time())
        s = self.state[str(self.chat_id)]

        # daily cap
        if s["daily_count"] >= self.daily_cap:
            return False, "daily cap reached"

        # min interval
        if now - s["last_sent_ts"] < self.min_interval:
            return False, "min interval"

        # dedupe on base text
        if base_text == s["last_base_message"] and now - s["last_sent_ts"] < self.dedupe_window:
            return False, "duplicate message"

        return True, ""

    def _mark_skipped(self):
        s = self.state[str(self.chat_id)]
        s["skipped_since_last_send"] = s.get("skipped_since_last_send", 0) + 1
        self._save_state()

    def _stamp(self) -> str:
        """Return a short human-readable timestamp."""
        return datetime.now().strftime("%d/%m %H:%M:%S")

    def send(self, text: str, parse_mode: Optional[str] = None, max_retries: int = 4):
        """
        Send a message with throttling, base-text dedupe, timestamp append, and a skip counter.
        If the message is skipped, returns {'ok': False, 'skipped': True, 'reason': ...}.
        On success, appends a timestamp and "(skipped N)" if any were skipped since last send.
        """
        base_text = text  # keep base text for dedupe
        with self.lock:
            ok, reason = self._can_send(base_text)
            if not ok:
                self._mark_skipped()
                return {"ok": False, "skipped": True, "reason": reason}

            # Compose final message
            final_text = base_text
            if self.append_timestamp:
                final_text += f"\n— {self._stamp()}"

            # If some messages were skipped since the last successful send, surface it
            s = self.state[str(self.chat_id)]
            skipped = int(s.get("skipped_since_last_send", 0))
            if skipped > 0:
                final_text += f"  (skipped {skipped})"

            payload = {"chat_id": self.chat_id, "text": final_text}
            if parse_mode:
                payload["parse_mode"] = parse_mode

            delay = 1.0
            for attempt in range(1, max_retries + 1):
                try:
                    r = requests.post(self.base_url, json=payload, timeout=10)
                    if r.status_code == 429:
                        # backoff if Telegram asks us to slow down
                        retry_after = None
                        try:
                            retry_after = r.json().get("parameters", {}).get("retry_after", None)
                        except Exception:
                            pass
                        time.sleep(int(retry_after) + 1 if retry_after else delay)
                        delay = min(delay * 2, 30)
                        continue

                    r.raise_for_status()
                    res = r.json()

                    # Update state on success
                    now = int(time.time())
                    s["last_sent_ts"] = now
                    s["daily_count"] = s.get("daily_count", 0) + 1
                    s["last_base_message"] = base_text
                    s["skipped_since_last_send"] = 0
                    s.setdefault("daily_reset_ts", now + 24*3600)
                    self._save_state()
                    return res

                except requests.RequestException:
                    if attempt == max_retries:
                        raise
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
