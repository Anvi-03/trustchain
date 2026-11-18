from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_hash', 'sender', 'receiver', 'amount', 'status', 'timestamp')
    list_filter = ('status', 'timestamp')
    readonly_fields = ('transaction_hash', 'signature', 'timestamp')
