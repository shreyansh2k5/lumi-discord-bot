# economy/transactions.py
# All Firestore read/write operations for the economy system.

from google.cloud import firestore
from economy.config import STARTING_BALANCE

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
    }
    await doc_ref.set(data)
    return data


async def update_user_data(user_id: str, data: dict) -> None:
    """Updates specific fields for a user."""
    await db.collection("users").document(user_id).update(data)


async def atomic_give(sender_id: str, receiver_id: str, amount: int) -> bool:
    """Safely transfers coins from sender to receiver in a single transaction."""
    transaction = db.transaction()

    @firestore.async_transactional
    async def _transfer(tx, sender_ref, receiver_ref, amt):
        sender_snap   = await sender_ref.get(transaction=tx)
        receiver_snap = await receiver_ref.get(transaction=tx)

        if sender_snap.get("coins") < amt:
            return False

        tx.update(sender_ref,   {"coins": sender_snap.get("coins")   - amt})
        tx.update(receiver_ref, {"coins": receiver_snap.get("coins") + amt})
        return True

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
        raider_coins = raider_snap.get("coins")
        target_coins = target_snap.get("coins")

        if win:
            tx.update(raider_ref, {"coins": raider_coins + amt})
            tx.update(target_ref, {"coins": target_coins - amt})
        else:
            tx.update(raider_ref, {"coins": raider_coins - amt})
            tx.update(target_ref, {"coins": target_coins + amt})
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
        if snap.get("coins") < cost:
            return False
        tx.update(user_ref, {
            "coins": snap.get("coins") - cost,
            "pets":  snap.get("pets", []) + [item],
        })
        return True

    user_ref = db.collection("users").document(user_id)
    return await _buy(transaction, user_ref, item_name, price)
