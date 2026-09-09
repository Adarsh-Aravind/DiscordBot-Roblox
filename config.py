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


def env_int(var: str, default: int = 0) -> int:
    """Parse an env var as an int ID, falling back to default if unset/invalid.

    Guards against an empty or malformed value (e.g. ``ALLOWED_YT_CHANNEL=``)
    raising ValueError at import time and stopping the bot from starting.
    """
    value = os.getenv(var, "").strip()
    return int(value) if value.isdigit() else default


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
COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", ".")

# --- Notification ping roles -----------------------------------------------
# Members opt into these roles themselves, so uploads and go-live alerts no
# longer need @everyone. Set either to 0 to fall back to no ping.
# The fallbacks are RUNE JERRY's server roles -- a fork should override both
# via the environment, same as OWNER_IDS and PROTECTED_USER_IDS above.
VIDEO_PING_ROLE_ID: int = env_int("VIDEO_PING_ROLE_ID", 1547335266233098381)
LIVE_PING_ROLE_ID: int = env_int("LIVE_PING_ROLE_ID", 1547335343685238795)

# --- Moderation logging ----------------------------------------------------
# Channel that automated moderation actions are reported to. 0 disables it.
MOD_LOG_CHANNEL_ID: int = env_int("MOD_LOG_CHANNEL_ID")

# --- Raid protection -------------------------------------------------------
# More than RAID_JOIN_THRESHOLD joins inside RAID_WINDOW_SECONDS triggers a
# lockdown (server verification level raised) for RAID_LOCKDOWN_MINUTES.
RAID_JOIN_THRESHOLD: int = env_int("RAID_JOIN_THRESHOLD", 10)
RAID_WINDOW_SECONDS: int = env_int("RAID_WINDOW_SECONDS", 60)
RAID_LOCKDOWN_MINUTES: int = env_int("RAID_LOCKDOWN_MINUTES", 15)

# --- Scam filter -----------------------------------------------------------
# Timeout applied when a scam link is caught.
SCAM_TIMEOUT_MINUTES: int = env_int("SCAM_TIMEOUT_MINUTES", 60)
# Accounts younger than this (in days) get their links removed. 0 disables.
NEW_ACCOUNT_LINK_DAYS: int = env_int("NEW_ACCOUNT_LINK_DAYS", 3)
