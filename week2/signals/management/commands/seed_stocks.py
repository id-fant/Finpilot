"""Management command: seed the Stock table with a starter NIFTY universe.

Run with:  python manage.py seed_stocks

WHY a management command (not an ad-hoc script): it is the production-grade
Django way to do one-off data tasks — it runs inside the Django context, is
discoverable via `manage.py help`, and is safe to re-run (idempotent below).
"""
from django.core.management.base import BaseCommand

from signals.models import Stock

# A small, liquid slice of the NIFTY 50 across a few sectors.
STARTER_UNIVERSE = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy Services", "IT"),
    ("INFY.NS", "Infosys", "IT"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"),
    ("ICICIBANK.NS", "ICICI Bank", "Banking"),
    ("SBIN.NS", "State Bank of India", "Banking"),
    ("ITC.NS", "ITC", "FMCG"),
    ("LT.NS", "Larsen & Toubro", "Infrastructure"),
]


class Command(BaseCommand):
    help = "Seed the Stock table with a starter NIFTY 50 universe."

    def handle(self, *args, **options) -> None:
        created = 0
        for symbol, name, sector in STARTER_UNIVERSE:
            # get_or_create makes this command safe to run repeatedly — an
            # existing stock is left untouched, not duplicated.
            _, was_created = Stock.objects.get_or_create(
                symbol=symbol,
                defaults={"name": name, "sector": sector},
            )
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded stocks: {created} created, "
            f"{len(STARTER_UNIVERSE) - created} already existed."
        ))
