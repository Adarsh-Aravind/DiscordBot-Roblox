"""Central configuration for the RuneJerry bot.

All IDs and tunable constants live here so cogs don't hard-code them.
Values are read from environment variables (see .env.example) with sensible
fallbacks for backwards compatibility.
"""

import os


def _parse_ids(*env_vars: str) -> set[int]:
    """Parse one or more comma-separated env vars into a set of int IDs."""
    ids: set[int] = set()
    for var in env_vars:
        for part in os.getenv(var, "").split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
    return ids


# --- Ownership -------------------------------------------------------------
# Users allowed to run owner-only commands.
OWNER_IDS: set[int] = _parse_ids("OWNER_ID", "OWNER_IDS") or {615174036733034538}

# Single "primary" owner used as the DM-relay target.
_primary = os.getenv("OWNER_ID", "").strip()
PRIMARY_OWNER_ID: int = int(_primary) if _primary.isdigit() else next(iter(OWNER_IDS))


def is_owner(user_id: int) -> bool:
    """Return True if the given user ID is a configured bot owner."""
    return user_id in OWNER_IDS


# --- Protected users -------------------------------------------------------
# Messages that mention any of these users are deleted with a warning.
# Defaults to RUNE JERRY's account so members can't ping the creator.
PROTECTED_USER_IDS: set[int] = _parse_ids("PROTECTED_USER_IDS") or {214331989774434305}

# --- General ---------------------------------------------------------------
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "#")
