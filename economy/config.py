# economy/config.py

LUNA_NAME       = "luna-coins"
STARTING_BALANCE = 10000
DAILY_REWARD    = 5000
BEG_MIN         = 100
BEG_MAX         = 1000

# Cooldowns (seconds)
RAID_COOLDOWN  = 3600   # 1 hour
DAILY_COOLDOWN = 86400  # 24 hours
BEG_COOLDOWN   = 300    # 5 minutes
BANK_COOLDOWN  = 86400  # 24 hours

# Raid
RAID_SUCCESS_CHANCE = 0.50
RAID_MAX_STEAL      = 0.25  # 25% of target wallet

# Blackjack
BJ_MAX_BET          = 50000
BJ_PAYOUT           = 2.0
BJ_BLACKJACK_PAYOUT = 2.5

# Pet Shop
PET_SHOP = {
    "dog":      {"price":   90_000, "emoji": "🐶"},
    "cat":      {"price":   70_000, "emoji": "🐱"},
    "hamster":  {"price": 1000_000, "emoji": "🐹"},
    "rabbit":   {"price":   15_000, "emoji": "🐰"},
    "parrot":   {"price":   12_000, "emoji": "🦜"},
    "horse":    {"price":   45_000, "emoji": "🐎"},
    "squirrel": {"price":   10_000, "emoji": "🐿️"},
    "goldfish": {"price":    7_000, "emoji": "🐠"},
    "eagle":    {"price":  100_000, "emoji": "🦅"},
    "lion":     {"price":  230_000, "emoji": "🦁"},
    "tiger":    {"price":  350_000, "emoji": "🐯"},
}
