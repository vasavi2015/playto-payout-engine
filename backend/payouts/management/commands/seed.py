from django.core.management.base import BaseCommand
from payouts.models import Merchant, BankAccount, LedgerEntry


class Command(BaseCommand):
    help = 'Seed merchants, bank accounts, and credit history.'

    def handle(self, *args, **options):
        data = [
            ('Acme Agency', 150000),
            ('Pixel Freelance Studio', 85000),
            ('Orbit Creators', 220000),
        ]
        for name, amount in data:
            merchant, _ = Merchant.objects.get_or_create(name=name)
            BankAccount.objects.get_or_create(
                merchant=merchant,
                defaults={'account_holder_name': name, 'account_number_last4': str(merchant.id).zfill(4)[-4:], 'ifsc': 'HDFC0001234'},
            )
            if not LedgerEntry.objects.filter(merchant=merchant, reference_id='seed-credit').exists():
                LedgerEntry.objects.create(merchant=merchant, amount_paise=amount, entry_type=LedgerEntry.CREDIT, reference_type='seed', reference_id='seed-credit', description='Simulated customer payment credit')
        self.stdout.write(self.style.SUCCESS('Seeded 3 merchants with bank accounts and credits.'))
