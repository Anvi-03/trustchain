from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from django.conf import settings

from . import services


@login_required
@require_http_methods(["GET", "HEAD", "POST"])
def mine_block(request):
    if request.method == "POST":
        try:
            block = services.mine_block(request.user.wallet.pk)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("mine_block")
        messages.success(request, f"Block #{block.index} mined. You earned {block.reward:.8f} MYC.")
        return redirect("block_detail", index=block.index)

    return render(request, "blockchain/mine.html", {
        "pending": services.mineable_transactions(),
        "reward": settings.MINING_REWARD,
    })
