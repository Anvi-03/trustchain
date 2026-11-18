from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from blockchain.models import Block
from blockchain.services import pending_transactions
from transactions.models import Transaction


@login_required
def home(request):
    wallet = request.user.wallet
    recent = Transaction.objects.filter(Q(sender=wallet) | Q(receiver=wallet))[:5]
    return render(request, "home.html", {
        "wallet": wallet,
        "recent": recent,
        "tip": Block.objects.last(),
        "block_count": Block.objects.count(),
        "pending_count": pending_transactions().count(),
    })
