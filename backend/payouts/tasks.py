import random
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import Payout, LedgerEntry


@shared_task
def process_payout(payout_id):
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if payout.status == Payout.COMPLETED or payout.status == Payout.FAILED:
            return payout.status
        if payout.status == Payout.PENDING:
            payout.transition_to(Payout.PROCESSING)
        payout.attempts += 1
        payout.last_attempt_at = timezone.now()
        payout.save(update_fields=['attempts', 'last_attempt_at', 'updated_at'])

    r = random.random()

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if payout.status != Payout.PROCESSING:
            return payout.status

        if r < 0.70:
            payout.transition_to(Payout.COMPLETED)
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount_paise=payout.amount_paise,
                entry_type=LedgerEntry.DEBIT,
                reference_type='payout',
                reference_id=str(payout.id),
                description='Finalize completed payout by consuming held funds',
            )
            return Payout.COMPLETED

        if r < 0.90:
            payout.fail_and_release_funds('Simulated bank failure')
            return Payout.FAILED

        delay_seconds = min(30 * (2 ** max(payout.attempts - 1, 0)), 300)
        payout.next_retry_at = timezone.now() + timedelta(seconds=delay_seconds)
        payout.save(update_fields=['next_retry_at', 'updated_at'])
        return Payout.PROCESSING


@shared_task
def retry_stuck_payouts():
    cutoff = timezone.now() - timedelta(seconds=30)
    stuck = Payout.objects.filter(status=Payout.PROCESSING, last_attempt_at__lte=cutoff)
    for payout in stuck:
        with transaction.atomic():
            locked = Payout.objects.select_for_update().get(id=payout.id)
            if locked.status != Payout.PROCESSING:
                continue
            if locked.attempts >= 3:
                locked.fail_and_release_funds('Max retry attempts exceeded')
            else:
                process_payout.delay(locked.id)
