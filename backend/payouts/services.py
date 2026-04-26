import hashlib
import json
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, F, Sum, When, BigIntegerField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from .models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyRecord


def request_hash(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def balance_query(merchant_id):
    return LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
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


def create_payout_with_idempotency(*, merchant_id, amount_paise, bank_account_id, idem_key):
    payload = {'amount_paise': amount_paise, 'bank_account_id': bank_account_id}
    hashed = request_hash(payload)

    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().get(id=merchant_id)

        try:
            idem, created = IdempotencyRecord.objects.select_for_update().get_or_create(
                merchant=merchant,
                key=idem_key,
                defaults={'request_hash': hashed, 'locked_until': timezone.now() + timedelta(seconds=30)},
            )
        except IntegrityError:
            idem = IdempotencyRecord.objects.select_for_update().get(merchant=merchant, key=idem_key)
            created = False

        if not created:
            if idem.is_expired:
                raise ValidationError('Idempotency-Key expired. Use a new UUID key.')
            if idem.request_hash != hashed:
                raise ValidationError('Same Idempotency-Key used with different request body.')
            if idem.is_complete:
                return idem.response_body, idem.status_code
            raise ValidationError('Request with this Idempotency-Key is still in progress. Retry after a few seconds.')

        if amount_paise <= 0:
            raise ValidationError('amount_paise must be positive.')

        bank_account = BankAccount.objects.select_for_update().get(id=bank_account_id, merchant=merchant)
        balances = balance_query(merchant.id)
        available = balances['available_balance_paise'] or 0

        if available < amount_paise:
            body = {'error': 'insufficient_balance', 'available_balance_paise': available}
            idem.response_body = body
            idem.status_code = 400
            idem.save(update_fields=['response_body', 'status_code', 'updated_at'])
            return body, 400

        payout = Payout.objects.create(
            merchant=merchant,
            bank_account=bank_account,
            amount_paise=amount_paise,
            status=Payout.PENDING,
        )
        LedgerEntry.objects.create(
            merchant=merchant,
            amount_paise=amount_paise,
            entry_type=LedgerEntry.HOLD,
            reference_type='payout',
            reference_id=str(payout.id),
            description='Hold funds for requested payout',
        )

        body = {
            'id': payout.id,
            'merchant_id': merchant.id,
            'amount_paise': payout.amount_paise,
            'bank_account_id': bank_account.id,
            'status': payout.status,
            'created_at': payout.created_at.isoformat(),
        }
        idem.response_body = body
        idem.status_code = 201
        idem.save(update_fields=['response_body', 'status_code', 'updated_at'])
        return body, 201
