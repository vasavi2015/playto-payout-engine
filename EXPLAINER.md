# EXPLAINER.md

## 1. The Ledger

### Balance calculation query

```python
LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
    available_balance_paise=Coalesce(
        Sum(
            Case(
                When(entry_type=LedgerEntry.CREDIT, then=F('amount_paise')),
                When(entry_type=LedgerEntry.RELEASE, then=F('amount_paise')),
                When(entry_type=LedgerEntry.HOLD, then=-F('amount_paise')),
                output_field=BigIntegerField(),
            )
        ),
        Value(0),
        output_field=BigIntegerField(),
    ),
    held_balance_paise=Coalesce(
        Sum(
            Case(
                When(entry_type=LedgerEntry.HOLD, then=F('amount_paise')),
                When(entry_type=LedgerEntry.DEBIT, then=-F('amount_paise')),
                When(entry_type=LedgerEntry.RELEASE, then=-F('amount_paise')),
                output_field=BigIntegerField(),
            )
        ),
        Value(0),
        output_field=BigIntegerField(),
    ),
)
```

I modelled money movement as immutable ledger entries instead of storing a mutable balance field. The merchant balance is derived from ledger entries using database aggregation.

The ledger has four entry types:

- `credit`: customer payment received for the merchant
- `hold`: funds reserved for a payout request
- `debit`: payout completed and held funds consumed
- `release`: failed payout, so held funds are returned

Available balance is:

```text
credits + releases - holds
```

Held balance is:

```text
holds - debits - releases
```

All amounts are stored as `BigIntegerField` in paise. There are no floats or decimals because payment systems should not depend on floating point arithmetic.

## 2. The Lock

### Exact code that prevents overdrawing

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)

    idem, created = IdempotencyRecord.objects.select_for_update().get_or_create(
        merchant=merchant,
        key=idem_key,
        defaults={'request_hash': hashed, 'locked_until': timezone.now() + timedelta(seconds=30)},
    )

    balances = balance_query(merchant.id)
    available = balances['available_balance_paise'] or 0

    if available < amount_paise:
        body = {'error': 'insufficient_balance', 'available_balance_paise': available}
        idem.response_body = body
        idem.status_code = 400
        idem.save(update_fields=['response_body', 'status_code', 'updated_at'])
        return body, 400

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        entry_type=LedgerEntry.HOLD,
        reference_type='payout',
        reference_id=str(payout.id),
        description='Hold funds for requested payout',
    )
```

This relies on PostgreSQL row-level locking using `SELECT ... FOR UPDATE`, exposed in Django through `select_for_update()`.

The merchant row is locked inside a database transaction. If two payout requests arrive at the same time for the same merchant, the second request waits until the first transaction commits. After the first request creates the `hold` ledger entry, the second request recalculates the balance from the database and sees the updated available balance. This prevents check-then-deduct race conditions.

## 3. The Idempotency

The system stores idempotency data in `IdempotencyRecord`.

```python
class IdempotencyRecord(models.Model):
    merchant = models.ForeignKey(Merchant, related_name='idempotency_records', on_delete=models.CASCADE)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    response_body = models.JSONField(null=True, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['merchant', 'key'], name='unique_idempotency_key_per_merchant')
        ]
```

The uniqueness constraint scopes keys per merchant. The same UUID can be used by different merchants, but not twice for the same merchant.

When a request arrives:

1. The request body is hashed.
2. The code locks or creates the idempotency record in the same transaction.
3. If the key already exists and the stored response is complete, the exact same response body and status code are returned.
4. If the key exists but the request body hash differs, the request is rejected.
5. If the first request is still in flight and the response has not been stored yet, the second request receives an in-progress error and can retry safely.

Keys expire after 24 hours using the `is_expired` property.

## 4. The State Machine

Illegal transitions are blocked in the `Payout` model.

```python
VALID_TRANSITIONS = {
    PENDING: {PROCESSING},
    PROCESSING: {COMPLETED, FAILED},
    COMPLETED: set(),
    FAILED: set(),
}


def can_transition_to(self, new_status):
    return new_status in self.VALID_TRANSITIONS.get(self.status, set())


def transition_to(self, new_status, failure_reason=''):
    if not self.can_transition_to(new_status):
        raise ValidationError(f'Illegal payout transition: {self.status} -> {new_status}')
    self.status = new_status
    if failure_reason:
        self.failure_reason = failure_reason
    self.save(update_fields=['status', 'failure_reason', 'updated_at'])
```

A failed-to-completed transition is blocked because `FAILED` maps to an empty set. A completed-to-pending transition is also blocked for the same reason.

Failed payout fund release is atomic:

```python
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
```

The status change and the ledger release happen in the same transaction.

## 5. The AI Audit

### Wrong code AI suggested

```python
merchant = Merchant.objects.get(id=merchant_id)
balance = get_balance(merchant)

if balance >= amount_paise:
    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        entry_type='hold'
    )
```

This looks correct in a single request, but it is wrong under concurrency. Two requests can read the same available balance before either inserts the hold ledger entry. Both can pass the balance check and overdraw the merchant.

### What I replaced it with

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    balances = balance_query(merchant.id)
    available = balances['available_balance_paise'] or 0

    if available < amount_paise:
        return {'error': 'insufficient_balance'}, 400

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        entry_type=LedgerEntry.HOLD,
        reference_type='payout',
        reference_id=str(payout.id),
    )
```

This version performs the check and hold inside one database transaction and locks the merchant row using PostgreSQL row-level locking. The second concurrent payout waits, then recalculates the balance after the first one commits.
