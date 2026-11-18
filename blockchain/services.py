from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from transactions.models import Transaction
from wallet.models import Wallet

from .models import Block, PROOF_PREFIX, calculate_block_hash


MAX_BALANCE = Decimal("999999999999.99999999")


def validate_chain():
    """Return the index of the first invalid block, or None for a valid chain."""
    blocks = Block.objects.prefetch_related("transactions__sender", "transactions__receiver")
    if not blocks:
        return 0

    previous_hash = "0"
    seen = set()

    for expected_index, block in enumerate(blocks):
        if block.index != expected_index:
            return expected_index
        if block.previous_hash != previous_hash or block.nonce < 0 or not block.is_valid():
            return block.index
        if block.index == 0:
            if block.nonce or block.reward or block.miner_address or block.transactions.all():
                return 0
        elif not (block.miner_address and block.reward > 0
                  and block.current_hash.startswith(PROOF_PREFIX)):
            return block.index

        for tx in block.transactions.all():
            if tx.pk in seen or tx.status != Transaction.STATUS_CONFIRMED or not tx.is_signed():
                return block.index
            seen.add(tx.pk)
        previous_hash = block.current_hash

    return None


def pending_transactions():
    return Transaction.objects.filter(status=Transaction.STATUS_PENDING, blocks__isnull=True).order_by(
        "timestamp", "pk"
    )


def select_transactions(pending, balances, wallets):
    """Apply eligible transfers in timestamp order to a temporary balance map."""
    selected = []
    for tx in pending:
        sender = tx.sender_id
        receiver = tx.receiver_id
        if not tx.amount.is_finite():
            continue
        if tx.amount > balances[sender] or balances[receiver] + tx.amount > MAX_BALANCE:
            continue
        if tx.is_signed(wallets[sender], wallets[receiver]):
            balances[sender] -= tx.amount
            balances[receiver] += tx.amount
            selected.append(tx)
    return selected


def mineable_transactions():
    pending = list(pending_transactions().select_related("sender", "receiver"))
    wallets = {wallet.pk: wallet for tx in pending for wallet in (tx.sender, tx.receiver)}
    balances = {pk: wallet.balance for pk, wallet in wallets.items()}
    return select_transactions(pending, balances, wallets)


@transaction.atomic
def mine_block(miner_id):
    # Lock the same row for every miner so concurrent requests take turns.
    Block.objects.select_for_update().filter(index=0).first()
    invalid_index = validate_chain()
    if invalid_index is not None:
        raise ValueError(f"Block #{invalid_index} is invalid. Mining stopped.")

    # Lock only Transaction rows because the pending query has an outer join.
    pending = list(pending_transactions().select_for_update(of=("self",)))
    wallet_ids = {miner_id}
    for tx in pending:
        wallet_ids.update((tx.sender_id, tx.receiver_id))
    wallets = {
        wallet.pk: wallet
        for wallet in Wallet.objects.filter(pk__in=wallet_ids).order_by("pk").select_for_update(no_key=True)
    }
    balances = {pk: wallet.balance for pk, wallet in wallets.items()}
    selected = select_transactions(pending, balances, wallets)
    reward = settings.MINING_REWARD
    balances[miner_id] += reward
    if balances[miner_id] > MAX_BALANCE:
        raise ValueError("The mining reward would exceed your wallet's balance limit.")

    tip = Block.objects.last()
    index = tip.index + 1
    timestamp = timezone.now()
    hashes = [tx.transaction_hash for tx in selected]
    miner_address = wallets[miner_id].address
    nonce = 0
    while True:
        block_hash = calculate_block_hash(
            index, timestamp, tip.current_hash, nonce, hashes, miner_address, reward,
        )
        if block_hash.startswith(PROOF_PREFIX):
            break
        nonce += 1

    block = Block.objects.create(
        index=index, timestamp=timestamp, previous_hash=tip.current_hash,
        current_hash=block_hash, nonce=nonce, miner_address=miner_address, reward=reward,
    )
    block.transactions.add(*selected)
    Transaction.objects.filter(pk__in=[tx.pk for tx in selected]).update(
        status=Transaction.STATUS_CONFIRMED
    )
    changed_wallets = []
    for pk, balance in balances.items():
        if wallets[pk].balance != balance:
            wallets[pk].balance = balance
            changed_wallets.append(wallets[pk])
    Wallet.objects.bulk_update(changed_wallets, ["balance"])
    return block
