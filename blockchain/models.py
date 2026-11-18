import hashlib
from django.db import models
from django.utils import timezone


def calculate_block_hash(index, timestamp, previous_hash, nonce=0, transaction_hashes=None):
    """
    Calculate the SHA-256 hash of a block's contents.

    Combines:
    - index: Position of the block in the chain
    - timestamp: When the block was created
    - previous_hash: Fingerprint of the previous block
    - nonce: Counter value for proof-of-work/identification
    - transaction_hashes: Ordered list of transactions in this block
    """
    if transaction_hashes:
        tx_str = ",".join(sorted(transaction_hashes))
    else:
        tx_str = "Genesis Block" if index == 0 else "Empty"

    payload = f"{index}:{timestamp}:{previous_hash}:{nonce}:{tx_str}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


class Block(models.Model):
    index = models.PositiveIntegerField(unique=True)
    timestamp = models.DateTimeField(default=timezone.now)
    transactions = models.ManyToManyField(
        'transactions.Transaction',
        related_name='blocks',
        blank=True
    )
    previous_hash = models.CharField(max_length=64, default="0")
    current_hash = models.CharField(max_length=64, unique=True)
    nonce = models.IntegerField(default=0)

    class Meta:
        ordering = ['index']

    def __str__(self):
        return f"Block #{self.index} [{self.current_hash[:10]}...]"

    def recalculate_hash(self):
        """Recompute block hash based on its stored data and attached transactions."""
        tx_hashes = list(self.transactions.values_list('transaction_hash', flat=True))
        return calculate_block_hash(
            index=self.index,
            timestamp=self.timestamp,
            previous_hash=self.previous_hash,
            nonce=self.nonce,
            transaction_hashes=tx_hashes
        )

    def is_valid(self):
        """Check if current hash matches recalculated hash."""
        return self.current_hash == self.recalculate_hash()

    @classmethod
    def get_or_create_genesis(cls):
        """
        Create or fetch the Genesis Block (Block #0).
        - Index: 0
        - Previous hash: "0"
        - Automatically computes its own current hash
        """
        genesis = cls.objects.filter(index=0).first()
        if genesis:
            return genesis

        timestamp = timezone.now()
        genesis_hash = calculate_block_hash(
            index=0,
            timestamp=timestamp,
            previous_hash="0",
            nonce=0,
            transaction_hashes=[]
        )

        genesis = cls.objects.create(
            index=0,
            timestamp=timestamp,
            previous_hash="0",
            current_hash=genesis_hash,
            nonce=0
        )
        return genesis

    @classmethod
    def add_block(cls, transactions=None, nonce=0):
        """
        Add a new block to the blockchain:
        1. Ensures Genesis block exists
        2. Retrieves the last block to link previous_hash
        3. Computes the new block's SHA-256 hash
        4. Saves block and attaches transactions
        5. Updates attached transactions status to Confirmed
        """
        cls.get_or_create_genesis()
        last_block = cls.objects.order_by('-index').first()

        new_index = last_block.index + 1
        previous_hash = last_block.current_hash
        timestamp = timezone.now()

        tx_list = list(transactions) if transactions else []
        tx_hashes = [tx.transaction_hash for tx in tx_list]

        current_hash = calculate_block_hash(
            index=new_index,
            timestamp=timestamp,
            previous_hash=previous_hash,
            nonce=nonce,
            transaction_hashes=tx_hashes
        )

        block = cls.objects.create(
            index=new_index,
            timestamp=timestamp,
            previous_hash=previous_hash,
            current_hash=current_hash,
            nonce=nonce
        )

        if tx_list:
            block.transactions.set(tx_list)
            for tx in tx_list:
                tx.status = 'Confirmed'
                tx.save()

        return block

    @classmethod
    def is_chain_valid(cls):
        """
        Validate integrity of the entire blockchain:
        - Genesis block must have index 0 and previous_hash '0'
        - Every block must have correct sequential index
        - Every block must store previous block's hash
        - Every block's stored current_hash must match recalculated hash
        """
        blocks = list(cls.objects.all().order_by('index').prefetch_related('transactions'))
        if not blocks:
            return True

        # Genesis validation
        if blocks[0].index != 0 or blocks[0].previous_hash != "0":
            return False

        for i in range(1, len(blocks)):
            prev_b = blocks[i - 1]
            curr_b = blocks[i]

            if curr_b.index != prev_b.index + 1:
                return False
            if curr_b.previous_hash != prev_b.current_hash:
                return False
            if not curr_b.is_valid():
                return False

        return True
