import hashlib

from django.db import models
from django.utils import timezone


PROOF_PREFIX = "000"


def calculate_block_hash(index, timestamp, previous_hash, nonce=0,
                         transaction_hashes=(), miner_address="", reward=0):
    """Hash the block header and its transaction fingerprints."""
    transactions = ",".join(sorted(transaction_hashes))
    transactions = transactions or ("Genesis Block" if index == 0 else "Empty")
    payload = f"{index}:{timestamp}:{previous_hash}:{nonce}:{transactions}"
    if index > 0:
        payload += f":{miner_address}:{reward:.8f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Block(models.Model):
    index = models.PositiveIntegerField(unique=True)
    timestamp = models.DateTimeField(default=timezone.now)
    transactions = models.ManyToManyField(
        "transactions.Transaction", related_name="blocks", blank=True
    )
    previous_hash = models.CharField(max_length=64, default="0")
    current_hash = models.CharField(max_length=64, unique=True)
    nonce = models.IntegerField(default=0)
    miner_address = models.CharField(max_length=66, blank=True, default="")
    reward = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    class Meta:
        ordering = ["index"]

    def __str__(self):
        return f"Block #{self.index} [{self.current_hash[:10]}…]"

    def recalculate_hash(self):
        return calculate_block_hash(
            self.index, self.timestamp, self.previous_hash, self.nonce,
            [tx.transaction_hash for tx in self.transactions.all()],
            self.miner_address, self.reward,
        )

    def is_valid(self):
        return self.current_hash == self.recalculate_hash()

    @classmethod
    def get_or_create_genesis(cls):
        timestamp = timezone.now()
        genesis, _ = cls.objects.get_or_create(
            index=0,
            defaults={
                "timestamp": timestamp,
                "current_hash": calculate_block_hash(0, timestamp, "0"),
            },
        )
        return genesis

    @classmethod
    def is_chain_valid(cls):
        from .services import validate_chain

        return validate_chain() is None
