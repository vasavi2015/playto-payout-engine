"""
Run after backend is up and seeded:
python scripts/concurrency_test.py

Expected: one request succeeds with 201 and one fails with 400 for merchant with ₹100 balance.
Edit MERCHANT_ID/BANK_ACCOUNT_ID if needed.
"""
import concurrent.futures
import uuid
import requests

BASE_URL = 'http://localhost:8000/api/v1'
MERCHANT_ID = 1
BANK_ACCOUNT_ID = 1
AMOUNT_PAISE = 6000


def make_request():
    return requests.post(
        f'{BASE_URL}/payouts/',
        headers={
            'Content-Type': 'application/json',
            'X-Merchant-Id': str(MERCHANT_ID),
            'Idempotency-Key': str(uuid.uuid4()),
        },
        json={'amount_paise': AMOUNT_PAISE, 'bank_account_id': BANK_ACCOUNT_ID},
        timeout=10,
    )


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(make_request) for _ in range(2)]
        for future in concurrent.futures.as_completed(futures):
            response = future.result()
            print(response.status_code, response.json())
