# RuneJerry Discord Bot

RuneJerry is a robust, fully-featured, and highly customizable Discord bot built with `discord.py`. Designed around a modular cog-based architecture, it provides seamless real-time utilities, server management, and community engagement features.

## Core Features

- **Roblox Profile Search**: Integrates directly with the public Roblox API to fetch and display real-time user accounts, avatars, join dates, and moderation statuses dynamically.
- **Interactive Giveaway System**: Facilitates server giveaways through persistent UI buttons. Features include automated winner selection, timed execution, and manual host control.
- **Automated Leveling**: Utilizes a persistent SQLite backend to track active chat participation, passively granting users XP and broadcasting level-up milestones.
- **YouTube Notifications**: Monitors specified YouTube channels and broadcasts rich embed notifications the moment new videos are uploaded.
- **Kick Notifications**: Polls a Kick channel and announces with a rich embed when the stream goes live.
- **Anti-Spam & Auto-Moderation**: Actively monitors text channels, automatically restricting excessive mentions, invite links, and spam behavior to preserve server integrity.
- **Direct Messaging Relay**: Intercepts direct messages sent to the bot and forwards them to the bot owner, allowing remote two-way communication.

## Prerequisites

- Python 3.8+
- A valid Discord Bot Token from the [Discord Developer Portal](https://discord.com/developers/applications)

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
   Populate the `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   OWNER_IDS=your_discord_id,additional_admin_id
   ```

4. **Initialize Database**:
   The bot utilizes `aiosqlite` for persistent, non-blocking storage. The required schemas (`runejerry.db`) will be generated automatically upon the first successful boot.

## Usage

Start the bot locally or on your hosting environment:
```bash
python main.py
```

### Command Reference

**Administrative Commands (Owner Only)**
- `#giveaway start <duration> <winners> <prize>`: Initiate an interactive giveaway.
- `#giveaway reroll <message_id>`: Manually reroll an ended giveaway.
- `#reply <user_id> <message>`: Prompt the bot to direct message a specific user.
- `#say <channel_id> <message>`: Prompt the bot to send a message to a specific channel.
- `#levelreset [user]`: Truncate XP for a specific user or the entire server.
- `#setpresence <type> <text>`: Dynamically update the bot's custom activity status.

**Public Commands**
- `#roblox <username>`: Query and display a public Roblox profile.
- `#rank`: Display current XP and level standings.
- `#help`: Render a comprehensive list of available modules and commands.
- `#status`: Fetch basic diagnostic metrics regarding the host Discord server.
- `#ping`: Evaluate and return the bot's current API latency.

## Architecture

RuneJerry employs a persistent, unblocking system using standard `asyncio` loop integration. The UI components (such as giveaway Join buttons) utilize Discord's persistent Views natively bound to predefined Custom IDs, ensuring they remain strictly continuous and functional even across bot restarts or fatal exceptions.
