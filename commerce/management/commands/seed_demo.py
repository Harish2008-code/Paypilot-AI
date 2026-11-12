from django.core.management.base import BaseCommand
from commerce.services.demo import seed_demo_data


class Command(BaseCommand):
    help = "Creates clearly-labelled catalog and PayPal-like demo records for local walkthroughs."

    def handle(self, *args, **options):
        result = seed_demo_data()
        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready: {result['products']} products, {result['payments_created']} new payment records, "
            f"invoice created={bool(result['invoice_created'])}."
        ))
