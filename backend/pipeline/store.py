"""In-memory session store for the dev API server.

Sessions hold real Python objects between stage calls (parsed IR, the
Digital Twin's cached reference run, etc.), so they cannot be round-tripped
through JSON between requests — a session lives in process memory for the
life of the dev server, bounded by MAX_SESSIONS (oldest evicted first).
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from .session import CompilationSession

MAX_SESSIONS = 50

_sessions: "OrderedDict[str, CompilationSession]" = OrderedDict()


def create(source: str, options=None) -> CompilationSession:
    s = CompilationSession(source, options)
    _sessions[s.id] = s
    _sessions.move_to_end(s.id)
    while len(_sessions) > MAX_SESSIONS:
        _sessions.popitem(last=False)
    return s


def get(session_id: str) -> Optional[CompilationSession]:
    s = _sessions.get(session_id)
    if s is not None:
        _sessions.move_to_end(session_id)
    return s


def delete(session_id: str) -> bool:
    return _sessions.pop(session_id, None) is not None


def count() -> int:
    return len(_sessions)
