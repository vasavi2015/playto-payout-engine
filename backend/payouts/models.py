from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone
from datetime import timedelta


class Merchant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    merchant = models.ForeignKey(Merchant, related_name='bank_accounts', on_delete=models.CASCADE)
    account_holder_name = models.CharField(max_length=255)
    account_number_last4 = models.CharField(max_length=4)
    ifsc = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.account_holder_name} ••••{self.account_number_last4}'


class LedgerEntry(models.Model):
    CREDIT = 'credit'
    DEBIT = 'debit'
    HOLD = 'hold'
    RELEASE = 'release'

    ENTRY_TYPES = [
        (CREDIT, 'Credit'),
        (DEBIT, 'Debit'),
        (HOLD, 'Hold'),
        (RELEASE, 'Release'),
    ]

    merchant = models.ForeignKey(Merchant, related_name='ledger_entries', on_delete=models.CASCADE)
    amount_paise = models.BigIntegerField()
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPES)
    reference_type = models.CharField(max_length=50, default='manual')
    reference_id = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['merchant', 'created_at'])]
        constraints = [models.CheckConstraint(check=Q(amount_paise__gt=0), name='ledger_amount_positive')]

    def __str__(self):
        return f'{self.merchant_id} {self.entry_type} {self.amount_paise}'


class Payout(models.Model):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

    STATUSES = [
        (PENDING, 'Pending'),
        (PROCESSING, 'Processing'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
    ]

    VALID_TRANSITIONS = {
        PENDING: {PROCESSING},
        PROCESSING: {COMPLETED, FAILED},
        COMPLETED: set(),
        FAILED: set(),
    }

    merchant = models.ForeignKey(Merchant, related_name='payouts', on_delete=models.CASCADE)
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount_paise = models.BigIntegerField()
    status = models.CharField(max_length=20, choices=STATUSES, default=PENDING)
    attempts = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'next_retry_at'])]
        constraints = [models.CheckConstraint(check=Q(amount_paise__gt=0), name='payout_amount_positive')]

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status, failure_reason=''):
        if not self.can_transition_to(new_status):
            raise ValidationError(f'Illegal payout transition: {self.status} -> {new_status}')
        self.status = new_status
        if failure_reason:
            self.failure_reason = failure_reason
        self.save(update_fields=['status', 'failure_reason', 'updated_at'])

    def fail_and_release_funds(self, reason):
        with transaction.atomic():
            locked = Payout.objects.select_for_update().get(id=self.id)
            locked.transition_to(Payout.FAILED, failure_reason=reason)
            LedgerEntry.objects.create(
                merchant=locked.merchant,
                amount_paise=locked.amount_paise,
                entry_type=LedgerEntry.RELEASE,
                reference_type='payout',
                reference_id=str(locked.id),
                description='Release held funds after payout failure',
            )


class IdempotencyRecord(models.Model):
    merchant = models.ForeignKey(Merchant, related_name='idempotency_records', on_delete=models.CASCADE)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    response_body = models.JSONField(null=True, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['merchant', 'key'], name='unique_idempotency_key_per_merchant')]
        indexes = [models.Index(fields=['merchant', 'key']), models.Index(fields=['created_at'])]

    @property
    def is_expired(self):
        return self.created_at < timezone.now() - timedelta(hours=24)

    @property
    def is_complete(self):
        return self.response_body is not None and self.status_code is not None
