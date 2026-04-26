from django.contrib import admin
from .models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyRecord

admin.site.register(Merchant)
admin.site.register(BankAccount)
admin.site.register(LedgerEntry)
admin.site.register(Payout)
admin.site.register(IdempotencyRecord)
