# economy/logic.py
# Pure game logic — no Discord, no database. Easy to unit-test.

import random
from economy.config import BEG_MIN, BEG_MAX, RAID_MAX_STEAL


def get_beg_earnings() -> int:
    return random.randint(BEG_MIN, BEG_MAX)


def process_flip(amount: int) -> tuple[bool, int]:
    """50/50 coin flip. Returns (win, coin_delta)."""
    win = random.random() < 0.5
    return win, amount if win else -amount


def process_roll(amount: int) -> tuple[int, bool, int]:
    """Dice roll. 6 = 5x profit jackpot. Returns (roll_value, is_jackpot, coin_delta)."""
    result = random.randint(1, 6)
    if result == 6:
        return result, True, amount * 5
    return result, False, -amount


def calculate_raid_result(raider_coins: int, target_coins: int, success: bool) -> int:
    """
    Calculates how many coins move in a raid.
    On success, steals up to 20% of the mean wallet — but never more than the
    target actually has (prevents negative balances).
    On failure, the raider pays the target a random penalty up to 10% of their
    own wallet as hush money.
    """
    if success:
        mean_balance = (raider_coins + target_coins) / 2.0
        limit = int(mean_balance * RAID_MAX_STEAL)
        # Never steal more than the target owns
        limit = min(limit, target_coins)
        if limit <= 0:
            return 0
        return random.randint(1, limit)
    else:
        # Failure: raider pays a penalty of up to 10% of their own wallet
        penalty_limit = int(raider_coins * 0.10)
        if penalty_limit <= 0:
            return 0
        return random.randint(1, penalty_limit)
