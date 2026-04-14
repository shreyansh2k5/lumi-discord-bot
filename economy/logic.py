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
    The maximum amount is 20% of the mean of both persons' balance.
    """
    mean_balance = (raider_coins + target_coins) / 2.0
    limit = int(mean_balance * RAID_MAX_STEAL)
    if limit <= 0:
        return 0
    return random.randint(1, limit)
