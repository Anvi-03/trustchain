from django.contrib import admin
from .models import Block


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ('index', 'current_hash', 'previous_hash', 'nonce', 'timestamp')
    readonly_fields = ('index', 'current_hash', 'previous_hash', 'nonce', 'timestamp')
    filter_horizontal = ('transactions',)
