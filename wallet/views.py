from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def wallet_detail(request):
    """Display the logged-in user's wallet dashboard."""
    wallet = request.user.wallet
    return render(request, 'wallet/detail.html', {'wallet': wallet})
