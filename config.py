# config.py
# Bot-wide constants. Non-secret values only — secrets stay in .env

# ── Bot ─────────────────────────────────────────────────────────
COMMAND_PREFIX = "$"

# ── Dead Chat Reviver ────────────────────────────────────────────
# The deadchat check runs every 5 minutes by default now.
# Guilds can set their own intervals via /deadchat interval

# ── AI ───────────────────────────────────────────────────────────
AI_MAX_TOKENS     = 200
AI_MAX_INPUT_CHARS = 400  # trim user input before sending to API
