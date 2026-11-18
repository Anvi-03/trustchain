import hashlib
from django.db import models
from django.utils import timezone
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

from wallet.models import Wallet


def calculate_transaction_hash(sender_address, receiver_address, amount, timestamp_str):
    """Calculate the SHA-256 hash of a transaction's details."""
    payload = f"{sender_address}:{receiver_address}:{amount}:{timestamp_str}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def sign_transaction(private_key_pem, message):
    """
    Digitally sign a message using the sender's private key.
    Uses RSA with PSS padding and SHA-256.
    """
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None
    )
    signature = private_key.sign(
        message.encode('utf-8'),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    return signature.hex()


def verify_transaction_signature(public_key_pem, message, signature_hex):
    """
    Verify a digital signature using the sender's public key.
    Uses RSA with PSS padding and SHA-256.
    """
    try:
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8')
        )
        public_key.verify(
            bytes.fromhex(signature_hex),
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


class Transaction(models.Model):
    STATUS_PENDING = 'Pending'
    STATUS_CONFIRMED = 'Confirmed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
    ]

    sender = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='sent_transactions'
    )
    receiver = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='received_transactions'
    )
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    transaction_hash = models.CharField(max_length=64, unique=True)
    signature = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Tx {self.transaction_hash[:10]}... ({self.amount} MYC: {self.status})"
