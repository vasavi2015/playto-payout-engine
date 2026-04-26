# Generated manually for challenge submission
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Merchant',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('name', models.CharField(max_length=255)), ('created_at', models.DateTimeField(auto_now_add=True))],
        ),
        migrations.CreateModel(
            name='BankAccount',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('account_holder_name', models.CharField(max_length=255)), ('account_number_last4', models.CharField(max_length=4)), ('ifsc', models.CharField(max_length=20)), ('created_at', models.DateTimeField(auto_now_add=True)), ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_accounts', to='payouts.merchant'))],
        ),
        migrations.CreateModel(
            name='LedgerEntry',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('amount_paise', models.BigIntegerField()), ('entry_type', models.CharField(choices=[('credit', 'Credit'), ('debit', 'Debit'), ('hold', 'Hold'), ('release', 'Release')], max_length=20)), ('reference_type', models.CharField(default='manual', max_length=50)), ('reference_id', models.CharField(max_length=100)), ('description', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ledger_entries', to='payouts.merchant'))],
        ),
        migrations.CreateModel(
            name='Payout',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('amount_paise', models.BigIntegerField()), ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20)), ('attempts', models.PositiveIntegerField(default=0)), ('last_attempt_at', models.DateTimeField(blank=True, null=True)), ('next_retry_at', models.DateTimeField(blank=True, null=True)), ('failure_reason', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)), ('bank_account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='payouts.bankaccount')), ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payouts', to='payouts.merchant'))],
        ),
        migrations.CreateModel(
            name='IdempotencyRecord',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('key', models.UUIDField()), ('request_hash', models.CharField(max_length=64)), ('response_body', models.JSONField(blank=True, null=True)), ('status_code', models.PositiveIntegerField(blank=True, null=True)), ('locked_until', models.DateTimeField(blank=True, null=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)), ('merchant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='idempotency_records', to='payouts.merchant'))],
        ),
        migrations.AddConstraint(model_name='ledgerentry', constraint=models.CheckConstraint(condition=models.Q(('amount_paise__gt', 0)), name='ledger_amount_positive')),
        migrations.AddIndex(model_name='ledgerentry', index=models.Index(fields=['merchant', 'created_at'], name='payouts_led_merchan_5d9f7a_idx')),
        migrations.AddConstraint(model_name='payout', constraint=models.CheckConstraint(condition=models.Q(('amount_paise__gt', 0)), name='payout_amount_positive')),
        migrations.AddIndex(model_name='payout', index=models.Index(fields=['status', 'next_retry_at'], name='payouts_pay_status_f35b65_idx')),
        migrations.AddConstraint(model_name='idempotencyrecord', constraint=models.UniqueConstraint(fields=('merchant', 'key'), name='unique_idempotency_key_per_merchant')),
        migrations.AddIndex(model_name='idempotencyrecord', index=models.Index(fields=['merchant', 'key'], name='payouts_ide_merchan_a6c26f_idx')),
        migrations.AddIndex(model_name='idempotencyrecord', index=models.Index(fields=['created_at'], name='payouts_ide_created_c56b96_idx')),
    ]
