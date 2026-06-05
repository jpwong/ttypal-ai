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
        # Check if the process is still alive
        pid = info.get("pid")
        if pid:
            try:
                os.kill(pid, 0)
            except (ProcessLookupError, PermissionError):
                # Process is dead, clean up
                path.unlink(missing_ok=True)
                return None
        return info
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def remove_session(name):
    """Remove session metadata file."""
    path = session_file(name)
    path.unlink(missing_ok=True)


def list_sessions():
    """List all active sessions. Returns [(name, info), ...]."""
    sessions = []
    for f in SESSION_DIR.glob("ttypal-*.session"):
        name = f.stem.replace("ttypal-", "")
        info = load_session(name)
        if info:
            sessions.append((name, info))
    return sorted(sessions, key=lambda x: x[0])


def find_socket(session=None, board=None):
    """Find the socket path for a session.

    - session: look up by session name directly
    - board: scan session files for matching profile
    - neither: auto-detect (must be exactly one session)

    Returns socket path string. Prints error and exits on failure.
    """
    import sys

    if session:
        info = load_session(session)
        if info:
            return info["socket"]
        print(f"Session '{session}' not found or not running", file=sys.stderr)
        sys.exit(1)

    sessions = list_sessions()

    if board:
        matches = [(name, info) for name, info in sessions if info.get("profile") == board]
        if len(matches) == 1:
            return matches[0][1]["socket"]
        if len(matches) > 1:
            print(f"Multiple sessions with profile '{board}', use -S to specify:", file=sys.stderr)
            for name, _ in matches:
                print(f"  {name}", file=sys.stderr)
            sys.exit(1)
        print(f"板子 '{board}' 的 ttypal 未运行 (未找到匹配的 session)", file=sys.stderr)
        sys.exit(1)

    # Auto-detect
    if len(sessions) == 1:
        return sessions[0][1]["socket"]
    if len(sessions) > 1:
        print("Multiple sessions running, use -b or -S to specify:", file=sys.stderr)
        for name, info in sessions:
            print(f"  {name} (profile: {info.get('profile', '?')})", file=sys.stderr)
        sys.exit(1)
    print("No active ttypal sessions found", file=sys.stderr)
    sys.exit(1)
