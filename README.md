# ✨ Lumi — Discord Bot

Lumi is a sweet, playful, and caring bot built to make your Discord server more fun, safer, and more active — with **AI chat**, **moderation**, **economy + games**, and **dead-chat revival**.

---

## ➕ Add Lumi to Your Server

Invite link: https://discord.com/oauth2/authorize?client_id=1387357109842350120&permissions=8&integration_type=0&scope=bot+applications.commands


**Steps**
1. Open the link above
2. Select the server you want to add Lumi to
3. Click **Authorize**
4. Complete the captcha (if prompted)

---

## 🌟 Features

### 💖 AI Chat
- Chat with Lumi by **pinging** her or **replying** to her messages.
- Friendly, supportive “bestie” personality.

### 🚫 Smart Auto‑Moderation
- **Per-server bad word filtering** (customizable per guild)
- **Role exceptions** (exclude certain roles from automod)
- Settings are persistent across restarts

### 🛡️ Moderation (Slash Commands)
- `/mute` and `/unmute`
- `/kick`
- `/ban`

### 💬 Dead Chat Revival
Bring life back when channels go quiet:
- `/deadchat add` — allow a channel for revival messages
- `/deadchat remove` — stop reviving in a channel
- `/deadchat view` — list configured channels
- `/deadchat interval` — set how long chat must be inactive before reviving
- Configure welcome messages from `/deadchat_configuration`; they are off by default and only send to the selected channel

### 💰 Economy + Games
Earn and play inside your server:
- Daily rewards, wallet/balance, giving coins, profiles
- Games like **blackjack**, **flip**, **roll**, and **raid**
- Leaderboard + pet shop system

Tip: use `$help` (or `/help`) to see everything in one place.

### 📊 Server Utilities
- `/status` — uptime, latency, server count
- `/server_info` — information about the current server

---

## 💡 Getting Started In-Server

- Type **`$help`** to see the full command list
- Use **`/status`** to confirm Lumi is online
- Configure moderation and dead-chat via the `/badword`, `/exception`, and `/deadchat` command groups

## 🛠️ Installation

### Configure environment variables

Create a `.env` file in the project root with the following values:

```dotenv
DISCORD_TOKEN=your_discord_bot_token
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
PRIMARY_PROVIDER=groq
FALLBACK_PROVIDER=openrouter
FIREBASE_SERVICE_ACCOUNT_KEY=your_firebase_service_account_json
BOT_OWNER_ID=your_discord_user_id
```

Keep `.env` private and never commit it. The Firebase service account value must be valid JSON on one line (the private key should contain escaped `\n` characters).

### 🐍 Run without Docker

Use this method if Python is installed on the host.

1. Install [Python 3.13](https://www.python.org/downloads/).
2. Clone the repository and open the project directory:

   ```powershell
   git clone https://github.com/shreyansh2k5/lumi-discord-bot.git
   cd lumi-discord-bot
   ```

3. Create and activate a virtual environment:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   On macOS or Linux, use:

   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. Create the `.env` file described above, then start Lumi:

   ```powershell
   python main.py
   ```

Keep the terminal open while the bot is running. Press `Ctrl+C` to stop it.

### 🐳 Run with Docker

Docker keeps the bot runtime isolated and automatically restarts it after a failure or host reboot.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
2. Clone the repository and open the project directory if you have not already:

   ```powershell
   git clone https://github.com/shreyansh2k5/lumi-discord-bot.git
   cd lumi-discord-bot
   ```

3. Create the `.env` file described above in the project root.
4. Build and start Lumi:

   ```powershell
   docker compose up -d --build
   ```

5. Follow the bot logs:

   ```powershell
   docker compose logs -f lumi
   ```

6. Stop the bot:

   ```powershell
   docker compose down
   ```

The container does not expose ports. Discord, OpenRouter, and Firebase connections are outbound connections initiated by the bot.
