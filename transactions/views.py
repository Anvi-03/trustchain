from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Q

from wallet.models import Wallet

from .models import (
    Transaction,
    calculate_transaction_hash,
    sign_transaction,
    verify_transaction_signature,
)
from .forms import TransactionForm


@login_required
@db_transaction.atomic
def send_transaction(request):
    """Create and submit a new cryptocurrency transaction."""
    sender_wallet = request.user.wallet

    if request.method == 'POST':
        sender_wallet = Wallet.objects.select_for_update(no_key=True).get(pk=sender_wallet.pk)
        form = TransactionForm(request.POST, sender_wallet=sender_wallet)
        if form.is_valid():
            receiver_wallet = form.receiver_wallet
            amount = form.cleaned_data['amount']
            timestamp = timezone.now()

            # 1. Generate SHA-256 transaction hash
            tx_hash = calculate_transaction_hash(
                sender_wallet.address,
                receiver_wallet.address,
                amount,
                str(timestamp)
            )

            # 2. Sign transaction with sender's private key
            signature = sign_transaction(sender_wallet.private_key, tx_hash)

            # 3. Verify signature using sender's public key before accepting
            is_valid = verify_transaction_signature(
                sender_wallet.public_key,
                tx_hash,
                signature
            )

            if not is_valid:
                messages.error(request, "Digital signature verification failed. Transaction rejected.")
                return render(request, 'transactions/send.html', {'form': form, 'wallet': sender_wallet})

            # 4. Save transaction with Pending status (no balance changes yet)
            transaction = Transaction.objects.create(
                sender=sender_wallet,
                receiver=receiver_wallet,
                amount=amount,
                transaction_hash=tx_hash,
                signature=signature,
                timestamp=timestamp,
                status=Transaction.STATUS_PENDING
            )

            messages.success(request, f"Transaction created successfully! Hash: {tx_hash[:16]}... (Status: Pending)")
            return redirect('transaction_detail', tx_hash=transaction.transaction_hash)
    else:
        form = TransactionForm(sender_wallet=sender_wallet)

    return render(request, 'transactions/send.html', {
        'form': form,
        'wallet': sender_wallet
    })


@login_required
def transaction_history(request):
    """Display sent and received transactions for the logged-in user."""
    user_wallet = request.user.wallet
    transactions = Transaction.objects.filter(
        Q(sender=user_wallet) | Q(receiver=user_wallet)
    ).select_related('sender__user', 'receiver__user')

    return render(request, 'transactions/history.html', {
        'transactions': transactions,
        'wallet': user_wallet
    })


@login_required
def transaction_detail(request, tx_hash):
    """Display full details of a specific transaction."""
    transaction = get_object_or_404(
        Transaction.objects.select_related('sender__user', 'receiver__user').filter(
            Q(sender__user=request.user) | Q(receiver__user=request.user)
            | Q(status=Transaction.STATUS_CONFIRMED)
        ),
        transaction_hash=tx_hash
    )
    return render(request, 'transactions/detail.html', {
        'transaction': transaction
    })
