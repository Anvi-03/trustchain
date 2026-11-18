from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.utils import timezone

from .models import calculate_block_hash


@receiver(post_migrate)
def create_genesis_block_on_migrate(sender, using, apps=None, **kwargs):
    if sender.name != "blockchain":
        return
    try:
        block_model = (apps or sender.apps).get_model("blockchain", "Block")
    except LookupError:
        return

    timestamp = timezone.now()
    block_model.objects.using(using).get_or_create(
        index=0,
        defaults={
            "timestamp": timestamp,
            "current_hash": calculate_block_hash(0, timestamp, "0"),
        },
    )
