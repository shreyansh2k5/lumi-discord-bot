# economy/transactions.py
# All Firestore read/write operations for the economy system.

import datetime
from google.cloud import firestore
from economy.config import STARTING_BALANCE, DAILY_TRANSFER_LIMIT

db = None


def set_economy_db(database_client):
    global db
    db = database_client


async def get_user_data(user_id: str) -> dict:
    """Fetches user data, creating a default profile if none exists."""
    doc_ref = db.collection("users").document(user_id)
    doc = await doc_ref.get()
    if doc.exists:
        return doc.to_dict()

    data = {
        "coins":           STARTING_BALANCE,
        "isBanked":        False,
        "lastBankDeposit": 0,
        "lastDaily":       0,
        "lastBeg":         0,
        "lastRaid":        0,
        "pets":            [],
        "dailyTransferDate": "",
        "dailySent":       0,
        "dailyReceived":   0,
    }
    await doc_ref.set(data)
    return data


async def update_user_data(user_id: str, data: dict) -> None:
    """Updates specific fields for a user."""
    await db.collection("users").document(user_id).update(data)


async def atomic_give(sender_id: str, receiver_id: str, amount: int, is_sender_owner: bool = False, is_receiver_owner: bool = False) -> tuple[bool, str]:
    """Safely transfers coins from sender to receiver in a single transaction."""
    transaction = db.transaction()

    @firestore.async_transactional
    async def _transfer(tx, sender_ref, receiver_ref, amt):
        sender_snap   = await sender_ref.get(transaction=tx)
        receiver_snap = await receiver_ref.get(transaction=tx)
        
        sender_data = sender_snap.to_dict() or {}
        receiver_data = receiver_snap.to_dict() or {}
        
        sender_coins = sender_data.get("coins", 0)
        receiver_coins = receiver_data.get("coins", STARTING_BALANCE)

        if sender_coins < amt:
            return False, "You don't have enough coins!"

        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        sender_date = sender_data.get("dailyTransferDate", "")
        sender_sent = sender_data.get("dailySent", 0)
        if sender_date != today_str:
            sender_sent = 0
            
        if not is_sender_owner and (sender_sent + amt > DAILY_TRANSFER_LIMIT):
            return False, f"You can only send up to {DAILY_TRANSFER_LIMIT:,} coins per day! (You have already sent {sender_sent:,} today)"

        receiver_date = receiver_data.get("dailyTransferDate", "")
        receiver_received = receiver_data.get("dailyReceived", 0)
        if receiver_date != today_str:
            receiver_received = 0
            
        if not is_receiver_owner and (receiver_received + amt > DAILY_TRANSFER_LIMIT):
            return False, f"The receiver can only receive up to {DAILY_TRANSFER_LIMIT:,} coins per day! (They have already received {receiver_received:,} today)"

        sender_updates = {
            "coins": sender_coins - amt,
            "dailyTransferDate": today_str,
            "dailySent": sender_sent + amt,
        }
        if sender_date != today_str:
            sender_updates["dailyReceived"] = 0

        receiver_updates = {
            "coins": receiver_coins + amt,
            "dailyTransferDate": today_str,
            "dailyReceived": receiver_received + amt,
        }
        if receiver_date != today_str:
            receiver_updates["dailySent"] = 0

        tx.set(sender_ref, sender_updates, merge=True)
        tx.set(receiver_ref, receiver_updates, merge=True)
        return True, ""

    sender_ref   = db.collection("users").document(sender_id)
    receiver_ref = db.collection("users").document(receiver_id)
    return await _transfer(transaction, sender_ref, receiver_ref, amount)


async def atomic_raid(raider_id: str, target_id: str, amount: int, success: bool) -> bool:
    """Moves coins between users for a raid attempt."""
    transaction = db.transaction()

    @firestore.async_transactional
    async def _raid(tx, raider_ref, target_ref, amt, win):
        raider_snap = await raider_ref.get(transaction=tx)
        target_snap = await target_ref.get(transaction=tx)
        
        r_data = raider_snap.to_dict() or {}
        t_data = target_snap.to_dict() or {}
        
        raider_coins = r_data.get("coins", STARTING_BALANCE)
        target_coins = t_data.get("coins", STARTING_BALANCE)

        if win:
            # Safety clamp: never steal more than the target currently has
            actual_amt = min(amt, max(target_coins, 0))
            tx.set(raider_ref, {"coins": raider_coins + actual_amt}, merge=True)
            tx.set(target_ref, {"coins": target_coins - actual_amt}, merge=True)
        else:
            # Safety clamp: never pay more penalty than the raider has
            actual_amt = min(amt, max(raider_coins, 0))
            tx.set(raider_ref, {"coins": raider_coins - actual_amt}, merge=True)
            tx.set(target_ref, {"coins": target_coins + actual_amt}, merge=True)
        return True

    raider_ref = db.collection("users").document(raider_id)
    target_ref = db.collection("users").document(target_id)
    return await _raid(transaction, raider_ref, target_ref, amount, success)


async def atomic_purchase(user_id: str, item_name: str, price: int) -> bool:
    """Deducts coins and adds a pet in a single atomic transaction."""
    transaction = db.transaction()

    @firestore.async_transactional
    async def _buy(tx, user_ref, item, cost):
        snap = await user_ref.get(transaction=tx)
        data = snap.to_dict() or {}
        if data.get("coins", 0) < cost:
            return False
        tx.set(user_ref, {
            "coins": data.get("coins", 0) - cost,
            "pets":  data.get("pets", []) + [item],
        }, merge=True)
        return True

    user_ref = db.collection("users").document(user_id)
    return await _buy(transaction, user_ref, item_name, price)
