from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_genesis_block_on_migrate(sender, **kwargs):
    """Automatically create the Genesis Block after database migrations run."""
    if sender.name == 'blockchain':
        from .models import Block
        Block.get_or_create_genesis()
