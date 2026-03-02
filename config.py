# config.py
# Bot-wide constants. Non-secret values only — secrets stay in .env

# ── Bot ─────────────────────────────────────────────────────────
COMMAND_PREFIX = "$"

# ── Dead Chat Reviver ────────────────────────────────────────────
DEAD_CHAT_CHECK_INTERVAL_MINUTES = 60   # check once per hour (saves CPU vs every 30min)

# ── AI ───────────────────────────────────────────────────────────
AI_MAX_TOKENS     = 300
AI_MAX_INPUT_CHARS = 500  # trim user input before sending to API
