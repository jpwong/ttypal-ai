"""Session metadata management for ttypal.

A session represents a running ttypal instance. Each session has a unique name
and is associated with a board profile and a physical serial port. Session
metadata is stored as JSON files in /tmp/ so that client tools can discover
active sessions and connect to them.
"""

import json
import os
from pathlib import Path

SESSION_DIR = Path("/tmp")


class SessionLookupError(Exception):
    """Base error for session/socket lookup failures."""


class SessionNotFound(SessionLookupError):
    """Named session does not exist or is not alive."""


class BoardSessionNotFound(SessionLookupError):
    """No active session matches the requested board profile."""


class MultipleSessionsFound(SessionLookupError):
    """Lookup is ambiguous because multiple sessions match."""


def session_file(name):
    """Return the path to a session metadata file."""
    return SESSION_DIR / f"ttypal-{name}.session"


def save_session(name, info):
    """Save session metadata to disk.

    info should be a dict with keys: profile, port, baudrate, socket, pid, started
    """
    path = session_file(name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)


def load_session(name):
    """Load session metadata from disk. Returns None if not found or invalid."""
    path = session_file(name)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            info = json.load(f)
        return info
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def is_session_alive(name):
    """Check if a session's process is still running."""
    info = load_session(name)
    if not info:
        return False
    pid = info.get("pid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except ProcessLookupError:
        return False


def remove_session(name, pid=None):
    """Remove session metadata file.

    If pid is given, only remove if the session file's PID matches
    (prevents one instance from deleting another's session file).
    """
    path = session_file(name)
    if not path.exists():
        return
    if pid is not None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                info = json.load(f)
            if info.get("pid") != pid:
                return  # Not our session, don't delete
        except (json.JSONDecodeError, OSError):
            pass
    path.unlink(missing_ok=True)


def list_sessions():
    """List all active sessions. Returns [(name, info), ...]."""
    sessions = []
    for f in SESSION_DIR.glob("ttypal-*.session"):
        name = f.stem.replace("ttypal-", "")
        info = load_session(name)
        if info and is_session_alive(name):
            sessions.append((name, info))
    return sorted(sessions, key=lambda x: x[0])


def resolve_socket(*, session=None, board=None):
    """Resolve the socket path for a session.

    - session: look up by session name directly
    - board: scan session files for matching profile
    - neither: auto-detect (must be exactly one session)

    Falls back to scanning /tmp/ttypal-*.sock files if no .session
    metadata exists (e.g. older interactive terminal instances).

    Returns socket path string. Raises SessionLookupError on failure.
    """
    if session and board:
        raise MultipleSessionsFound("Use either session or board, not both")

    if session:
        info = load_session(session)
        if info and is_session_alive(session):
            return info["socket"]
        # Fallback: check if .sock file exists and is a live socket
        sock_path = SESSION_DIR / f"ttypal-{session}.sock"
        if sock_path.exists():
            return str(sock_path)
        raise SessionNotFound(f"Session '{session}' not found or not running")

    sessions = list_sessions()

    if board:
        matches = [(name, info) for name, info in sessions if info.get("profile") == board]
        if len(matches) == 1:
            return matches[0][1]["socket"]
        if len(matches) > 1:
            names = ", ".join(name for name, _ in matches)
            raise MultipleSessionsFound(
                f"Multiple sessions with profile '{board}', use -S to specify: {names}"
            )
        # Fallback: check .sock file by board name
        sock_path = SESSION_DIR / f"ttypal-{board}.sock"
        if sock_path.exists():
            return str(sock_path)
        raise BoardSessionNotFound(
            f"板子 '{board}' 的 ttypal 未运行 (未找到匹配的 session)"
        )

    # Auto-detect
    if len(sessions) == 1:
        return sessions[0][1]["socket"]
    if len(sessions) > 1:
        details = ", ".join(
            f"{name} (profile: {info.get('profile', '?')})" for name, info in sessions
        )
        raise MultipleSessionsFound(
            f"Multiple sessions running, use -b or -S to specify: {details}"
        )

    # Fallback: scan for .sock files without .session metadata
    sock_files = list(SESSION_DIR.glob("ttypal-*.sock"))
    if len(sock_files) == 1:
        return str(sock_files[0])
    if len(sock_files) > 1:
        details = ", ".join(str(s) for s in sock_files)
        raise MultipleSessionsFound(
            "Multiple ttypal sockets found (no session metadata), "
            f"use --socket to specify: {details}"
        )

    raise SessionNotFound("No active ttypal sessions found")


def find_socket(session=None, board=None):
    """Find the socket path for a session.

    CLI compatibility wrapper around resolve_socket(). Prints errors and exits
    on failure.
    """
    import sys

    try:
        return resolve_socket(session=session, board=board)
    except SessionLookupError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
