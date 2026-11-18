from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blockchain.models import Block
from blockchain.services import validate_chain
from transactions.models import Transaction


@login_required
def explorer(request):
    blocks = Block.objects.annotate(transaction_count=Count("transactions")).order_by("-index")
    return render(request, "explorer/index.html", {"blocks": blocks})


@login_required
def block_detail(request, index):
    blocks = Block.objects.prefetch_related("transactions")
    block = get_object_or_404(blocks, index=index)
    return render(request, "explorer/block.html", {"ledger_block": block})


@login_required
def explorer_transaction(request, tx_hash):
    tx = get_object_or_404(
        Transaction.objects.select_related("sender__user", "receiver__user").distinct(),
        transaction_hash=tx_hash,
        status=Transaction.STATUS_CONFIRMED,
        blocks__isnull=False,
    )
    return render(request, "transactions/detail.html", {
        "transaction": tx,
        "ledger_block": tx.blocks.first(),
    })


@login_required
@require_POST
def validate(request):
    invalid_index = validate_chain()
    if invalid_index is None:
        messages.success(request, "Blockchain is valid.")
    else:
        messages.error(request, f"Blockchain is invalid at block #{invalid_index}.")
    return redirect("explorer")
