import hashlib

from django.db import models
from django.contrib.auth.models import User
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


def generate_key_pair():
    """
    Generate an RSA 2048-bit key pair.

    How it works:
    1. RSA generates two mathematically linked keys — a private key and a public key.
    2. The private key is kept secret (used to sign transactions later).
    3. The public key can be shared freely (used to verify signatures later).
    4. We serialize both keys to PEM format (a text-based encoding) for storage.

    Returns:
        tuple: (private_key_pem, public_key_pem) as strings.
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')

    return private_pem, public_pem


def generate_wallet_address(public_key_pem):
    """
    Generate a unique wallet address from the public key using SHA-256.

    How it works:
    1. Take the public key PEM string.
    2. Hash it with SHA-256 to produce a 64-character hex digest.
    3. Prefix it with "MC" (MyCoin) for readability.

    This guarantees each wallet gets a unique address derived from its unique public key.

    Returns:
        str: Wallet address like "MC7a3b9f..."
    """
    sha256_hash = hashlib.sha256(public_key_pem.encode('utf-8')).hexdigest()
    return f"MC{sha256_hash}"


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    address = models.CharField(max_length=66, unique=True)
    public_key = models.TextField()
    private_key = models.TextField()
    balance = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet ({self.address[:12]}...)"

    def save(self, *args, **kwargs):
        # Generate keys and address only for new wallets
        if not self.public_key:
            self.private_key, self.public_key = generate_key_pair()
        if not self.address:
            self.address = generate_wallet_address(self.public_key)
        super().save(*args, **kwargs)
