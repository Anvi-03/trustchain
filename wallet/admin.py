from django.contrib import admin

from .models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'address', 'balance', 'created_at')
    readonly_fields = ('address', 'public_key', 'created_at')
    # Private key is excluded from admin entirely
    exclude = ('private_key',)
