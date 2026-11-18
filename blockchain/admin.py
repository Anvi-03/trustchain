from django.contrib import admin

from .models import Block


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("index", "current_hash", "previous_hash", "nonce", "timestamp")
    readonly_fields = (
        "index", "current_hash", "previous_hash", "nonce", "timestamp",
        "transactions", "miner_address", "reward",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
