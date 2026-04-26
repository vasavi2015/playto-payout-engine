import threading
import uuid
import pytest
from django.test import TransactionTestCase, Client
from payouts.models import Merchant, BankAccount, LedgerEntry, Payout


class PayoutConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.merchant = Merchant.objects.create(name='Race Merchant')
        self.bank = BankAccount.objects.create(merchant=self.merchant, account_holder_name='Race Merchant', account_number_last4='1111', ifsc='HDFC0001111')
        LedgerEntry.objects.create(merchant=self.merchant, amount_paise=10000, entry_type=LedgerEntry.CREDIT, reference_type='test', reference_id='credit-1')

    def test_two_parallel_60_rupee_payouts_only_one_succeeds(self):
        results = []
        barrier = threading.Barrier(2)

        def hit_api():
            client = Client()
            barrier.wait()
            response = client.post(
                '/api/v1/payouts/',
                data={'amount_paise': 6000, 'bank_account_id': self.bank.id},
                content_type='application/json',
                HTTP_X_MERCHANT_ID=str(self.merchant.id),
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            )
            results.append(response.status_code)

        t1 = threading.Thread(target=hit_api)
        t2 = threading.Thread(target=hit_api)
        t1.start(); t2.start(); t1.join(); t2.join()

        assert sorted(results) == [201, 400]
        assert Payout.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_idempotency_returns_same_response_and_no_duplicate_payout(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    merchant = Merchant.objects.create(name='Idem Merchant')
    bank = BankAccount.objects.create(merchant=merchant, account_holder_name='Idem Merchant', account_number_last4='2222', ifsc='HDFC0002222')
    LedgerEntry.objects.create(merchant=merchant, amount_paise=10000, entry_type=LedgerEntry.CREDIT, reference_type='test', reference_id='credit-1')

    key = str(uuid.uuid4())
    client = Client()
    kwargs = dict(
        data={'amount_paise': 3000, 'bank_account_id': bank.id},
        content_type='application/json',
        HTTP_X_MERCHANT_ID=str(merchant.id),
        HTTP_IDEMPOTENCY_KEY=key,
    )
    r1 = client.post('/api/v1/payouts/', **kwargs)
    r2 = client.post('/api/v1/payouts/', **kwargs)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()['id'] == r2.json()['id']
    assert Payout.objects.count() == 1
