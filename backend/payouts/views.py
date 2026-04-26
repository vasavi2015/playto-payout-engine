from uuid import UUID
from django.core.exceptions import ValidationError
from django.db.models import Case, F, Sum, When, BigIntegerField, Value
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Merchant, LedgerEntry, Payout, BankAccount
from .serializers import MerchantSerializer, LedgerEntrySerializer, PayoutSerializer, BankAccountSerializer, PayoutCreateSerializer
from .services import balance_query, create_payout_with_idempotency
from .tasks import process_payout


def merchant_from_header(request):
    merchant_id = request.headers.get('X-Merchant-Id') or request.query_params.get('merchant_id')
    if not merchant_id:
        raise ValidationError('X-Merchant-Id header is required.')
    return int(merchant_id)


@api_view(['GET'])
def merchants(request):
    qs = Merchant.objects.all().order_by('id')
    return Response(MerchantSerializer(qs, many=True).data)


@api_view(['GET'])
def bank_accounts(request):
    merchant_id = merchant_from_header(request)
    qs = BankAccount.objects.filter(merchant_id=merchant_id).order_by('id')
    return Response(BankAccountSerializer(qs, many=True).data)


@api_view(['GET'])
def dashboard(request):
    merchant_id = merchant_from_header(request)
    Merchant.objects.get(id=merchant_id)
    balances = balance_query(merchant_id)
    ledger = LedgerEntry.objects.filter(merchant_id=merchant_id).order_by('-created_at')[:20]
    payouts = Payout.objects.filter(merchant_id=merchant_id).order_by('-created_at')[:20]
    return Response({
        'available_balance_paise': balances['available_balance_paise'] or 0,
        'held_balance_paise': balances['held_balance_paise'] or 0,
        'recent_ledger': LedgerEntrySerializer(ledger, many=True).data,
        'payouts': PayoutSerializer(payouts, many=True).data,
    })


@api_view(['POST', 'GET'])
def payouts(request):
    merchant_id = merchant_from_header(request)

    if request.method == 'GET':
        qs = Payout.objects.filter(merchant_id=merchant_id).order_by('-created_at')
        return Response(PayoutSerializer(qs, many=True).data)

    idem_key = request.headers.get('Idempotency-Key')
    if not idem_key:
        return Response({'error': 'Idempotency-Key header is required.'}, status=400)
    try:
        UUID(idem_key)
    except ValueError:
        return Response({'error': 'Idempotency-Key must be a UUID.'}, status=400)

    serializer = PayoutCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        body, status_code = create_payout_with_idempotency(
            merchant_id=merchant_id,
            amount_paise=serializer.validated_data['amount_paise'],
            bank_account_id=serializer.validated_data['bank_account_id'],
            idem_key=idem_key,
        )
        if status_code == 201:
            process_payout.delay(body['id'])
        return Response(body, status=status_code)
    except ValidationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
