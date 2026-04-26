from rest_framework import serializers
from .models import Merchant, BankAccount, LedgerEntry, Payout


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ['id', 'name']


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ['id', 'merchant', 'account_holder_name', 'account_number_last4', 'ifsc']


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'amount_paise', 'entry_type', 'reference_type', 'reference_id', 'description', 'created_at']


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = ['id', 'merchant', 'bank_account', 'amount_paise', 'status', 'attempts', 'failure_reason', 'created_at', 'updated_at']


class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.IntegerField(min_value=1)
