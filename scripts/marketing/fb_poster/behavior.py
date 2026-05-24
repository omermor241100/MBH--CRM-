"""
Behavioral randomizer — makes the bot's long-term pattern look human.

Handles:
  - Startup jitter (don't always fire at :00)
  - Random session skip (not every hour)
  - Variable posts per session (not always exactly 4)
  - Off days (2 random days/week with no activity)
  - Activity log for pattern analysis
"""

import random
import time
import json
import os
import requests as _req
from datetime import datetime, date


STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'logs', 'behavior_state.json')


def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(s: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


# ── Off days ────────────────────────────────────────────────────

def is_off_day() -> bool:
    return date.today().weekday() == 5  # שבת בלבד (5=Sat)


# ── Startup jitter ───────────────────────────────────────────────

def startup_jitter(max_minutes: int = 15, dry_run: bool = False):
    """
    Sleep a random amount before starting.
    Means: LaunchAgent fires at :00, but script starts at :03, :11, :07...
    Makes the hourly pattern invisible to Facebook's timing analysis.
    """
    if dry_run:
        return
    jitter_sec = random.randint(30, max_minutes * 60)
    m, s = divmod(jitter_sec, 60)
    print(f"  [⏱️] ג'יטר: ממתין {m}:{s:02d} לפני התחלה...")
    time.sleep(jitter_sec)


# ── Session skip ─────────────────────────────────────────────────

def should_skip_session(skip_probability: float = 0.15) -> bool:
    """
    15% of the time, skip this session entirely.
    Humans don't post every single hour — some hours they're busy.
    """
    return random.random() < skip_probability


# ── Variable session size ────────────────────────────────────────

def session_post_count(base: int = 4) -> int:
    """
    Return how many posts to make this session.
    Distributed around base: sometimes 2, sometimes 3, sometimes 4.
    Never always exactly the same number.
    """
    weights = {
        2: 0.20,   # 20% of sessions: 2 posts
        3: 0.35,   # 35%: 3 posts
        4: 0.30,   # 30%: 4 posts
        5: 0.10,   # 10%: 5 posts (rare)
        1: 0.05,   # 5%: 1 post (very rare)
    }
    counts = list(weights.keys())
    probs  = list(weights.values())
    return random.choices(counts, probs)[0]


# ── Master guard — call this at the start of every session ──────

def should_run(dry_run: bool = False) -> tuple[bool, str]:
    """
    Returns (should_run, reason).
    Call at startup — if False, exit immediately.
    """
    if is_off_day():
        days = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
        day = days[date.today().weekday()]
        return False, f"יום מנוחה ({day}) — לא מפרסמים היום"

    if not dry_run and should_skip_session():
        return False, "דילוג אקראי על session זה (15% הסתברות)"

    return True, "ok"


# ── Log session outcome ──────────────────────────────────────────

def check_ip_consistency() -> tuple[bool, str]:
    """
    Verify the public IP hasn't changed since last run.
    IP change = Facebook sees a new device = risk of 2FA / checkpoint.
    Returns (ok: bool, message: str).
    """
    try:
        r = _req.get('https://api.ipify.org?format=json', timeout=8)
        current_ip = r.json()['ip']
    except Exception as e:
        return True, f"לא ניתן לבדוק IP ({e}) — ממשיך"

    state    = _load_state()
    saved_ip = state.get('last_ip')

    if not saved_ip:
        state['last_ip'] = current_ip
        _save_state(state)
        return True, f"IP ראשוני נשמר: {current_ip}"

    if current_ip != saved_ip:
        state['last_ip'] = current_ip
        _save_state(state)
        return False, f"⚠️ IP השתנה! {saved_ip} → {current_ip} — סיכון גבוה לחסימה"

    return True, f"✓ IP תקין: {current_ip}"


def log_session(posts_ok: int, posts_failed: int):
    state = _load_state()
    history = state.get('session_history', [])
    history.append({
        'ts': datetime.now().isoformat(),
        'ok': posts_ok,
        'failed': posts_failed,
    })
    state['session_history'] = history[-50:]  # keep last 50
    _save_state(state)
