# RuneJerry Discord Bot

RuneJerry is a robust, fully-featured, and highly customizable Discord bot built with `discord.py`. Designed around a modular cog-based architecture, it provides seamless real-time utilities, server management, and community engagement features.

## Core Features

- **Roblox Profile Search**: Integrates directly with the public Roblox API to fetch and display real-time user accounts, avatars, join dates, and moderation statuses dynamically.
- **Interactive Giveaway System**: Facilitates server giveaways through persistent UI buttons. Features include automated winner selection, timed execution, and manual host control.
- **Automated Leveling**: Utilizes a persistent SQLite backend to track active chat participation, passively granting users XP and broadcasting level-up milestones.
- **YouTube Notifications**: Monitors specified YouTube channels and broadcasts rich embed notifications the moment new videos are uploaded.
- **Kick Notifications**: Polls a Kick channel and announces with a rich embed when the stream goes live.
- **Opt-In Ping Roles**: Members self-assign notification roles from a button panel, so announcements never need `@everyone`.
- **Auto-Threads**: Every upload and go-live announcement opens its own discussion thread, keeping chatter out of the main channel.
- **Anti-Spam & Auto-Moderation**: Actively monitors text channels, automatically restricting excessive mentions, invite links, and spam behavior to preserve server integrity.
- **Scam & Phishing Filter**: Detects lookalike domains impersonating Discord, Roblox, Steam and friends, plus classic bait wording paired with an unrecognised link.
- **Raid Protection**: Detects join-rate spikes and temporarily raises the server verification level, restoring the previous level automatically.
- **Moderation Audit Log**: Every automated action is reported to a log channel so you can tell a working filter from one that is misfiring.
- **Direct Messaging Relay**: Intercepts direct messages sent to the bot and forwards them to the bot owner, allowing remote two-way communication.

## Prerequisites

- Python 3.10+ (the codebase uses `X | None` type syntax)
- A valid Discord Bot Token from the [Discord Developer Portal](https://discord.com/developers/applications)

### Required Discord configuration

These are set in the Discord Developer Portal and server settings, **not** in `.env`:

| Requirement | Where | Why |
|---|---|---|
| **Server Members Intent** | Developer Portal → Bot → Privileged Gateway Intents | Raid protection counts joins. **The bot refuses to start without it.** |
| **Message Content Intent** | Same page | Command parsing and message filtering. |
| Manage Server | Bot role permissions | Raising the verification level during a lockdown. |
| Manage Roles | Bot role permissions | Assigning ping roles. The bot's role must sit **above** both ping roles. |
| Create Public Threads | Bot role permissions | Auto-threads on announcements. |
| Ping roles Mentionable | Server Settings → Roles | Otherwise the ping posts but notifies nobody. Alternatively grant the bot "Mention @everyone, @here and All Roles". |

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Adarsh-Aravind/DiscordBot-Roblox.git
   cd DiscordBot-Roblox
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill it in. The file is gitignored and must never be committed or bundled into a deploy archive.
   ```bash
   cp .env.example .env
   ```
   At minimum you must set `DISCORD_TOKEN` and the `YT_CHANNEL_*` destinations. Every variable is documented inline in `.env.example`; anything left at `0` disables that feature rather than erroring.

4. **Initialize Database**:
   The bot utilizes `aiosqlite` for persistent, non-blocking storage. The required schemas (`runejerry.db`) will be generated automatically upon the first successful boot.

## Usage

Start the bot locally or on your hosting environment:
```bash
python main.py
```

`app.py` is an equivalent entry point. For Linux deployment under systemd, see [deployment/README_LINUX.md](deployment/README_LINUX.md).

### Command Reference

`.help` is generated from the live command registry, so it always reflects what is actually loaded. The list below is a convenience copy.

**Administrative Commands (Owner Only)**
- `.giveaway start <duration> <winners> <prize>`: Initiate an interactive giveaway.
- `.giveaway reroll <message_id>`: Manually reroll an ended giveaway.
- `.reply <user_id> <message>`: Prompt the bot to direct message a specific user.
- `.say <channel_id> <message>`: Prompt the bot to send a message to a specific channel.
- `.levelreset [user]`: Truncate XP for a specific user or the entire server.
- `.pingroles`: Post the notification role opt-in panel.
- `.lockdown [minutes]`: Manually raise the server verification level.
- `.unlock`: Lift an active lockdown early.

**Public Commands**
- `.roblox <username>` (`.rbx`, `.rblx`): Query and display a public Roblox profile.
- `.rank`: Display current XP and level standings.
- `.leaderboard` (`.top`, `.lb`): Show the top 10 members by XP.
- `.help`: Render a comprehensive list of available modules and commands.
- `.ping`: Evaluate and return the bot's current API latency.

The command prefix defaults to `.` and is configurable via `COMMAND_PREFIX`.

## Moderation Behaviour

| Trigger | Action |
|---|---|
| Lookalike / phishing domain | Delete + timeout (`SCAM_TIMEOUT_MINUTES`, default 60) |
| Bait wording + unrecognised link | Delete + timeout |
| Link from account newer than `NEW_ACCOUNT_LINK_DAYS` | Delete + warning, no timeout |
| `@everyone`, mass mentions, invites, emoji spam | Delete + timeout (5 min) |
| Pinging a protected user | Delete + warning |
| `RAID_JOIN_THRESHOLD` joins within `RAID_WINDOW_SECONDS` | Verification raised to highest for `RAID_LOCKDOWN_MINUTES` |

Owners, administrators and anyone with Manage Messages bypass the spam filters. Links to official domains never count as evidence on their own, so members discussing or warning about scams are not punished for it.

Set `MOD_LOG_CHANNEL_ID` to receive a report of every automated action. Left at `0`, the bot moderates silently.

## Architecture

RuneJerry employs a persistent, unblocking system using standard `asyncio` loop integration. The UI components (such as giveaway Join buttons and the ping-role panel) utilize Discord's persistent Views natively bound to predefined Custom IDs, ensuring they remain strictly continuous and functional even across bot restarts or fatal exceptions.

Configuration lives in `config.py`, which reads every tunable from the environment with safe fallbacks — a malformed or empty value degrades to a default rather than crashing the bot at import time.

Background pollers are `discord.ext.tasks` loops. Because an unhandled `HTTPException` permanently stops such a loop, every network and send path inside them is guarded and logged so a single failure cannot silently disable notifications.

### Layout

```
app.py / main.py      entry points, intents, extension loading, error handling
config.py             all environment-derived settings
modlog.py             shared moderation audit-log helper
cogs/
  general.py          ping, generated help
  leveling.py         XP, rank, leaderboard
  roblox.py           Roblox profile lookup
  giveaway.py         giveaway system
  messaging.py        DM relay, owner send commands
  antispam.py         spam, invite, scam and phishing filtering
  raid.py             join-rate raid detection and lockdown
  pingroles.py        self-assignable notification roles
  youtube.py          upload notifications
  kick.py             go-live notifications
```
