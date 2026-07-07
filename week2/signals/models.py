"""Database models for the `signals` app: Stock and Signal."""
from django.db import models


class Stock(models.Model):
    """A security under coverage, e.g. RELIANCE.NS."""

    symbol = models.CharField(max_length=20, unique=True)  # e.g. "RELIANCE.NS"
    name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, blank=True)
    is_tracked = models.BooleanField(
        default=True,
        help_text="Untick to skip this stock in the daily job without deleting "
                  "its signal history.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["symbol"]

    def __str__(self) -> str:
        return f"{self.symbol} ({self.name})"


class Signal(models.Model):
    """One BUY/SELL/HOLD decision for one stock on one date."""

    SIGNAL_CHOICES = [("BUY", "Buy"), ("SELL", "Sell"), ("HOLD", "Hold")]

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="signals",
    )
    date = models.DateField()
    signal_type = models.CharField(max_length=4, choices=SIGNAL_CHOICES)
    # WHY DecimalField, not FloatField, for price: floats are binary and cannot
    # represent decimal fractions exactly (0.1 + 0.2 != 0.3). For money that
    # causes rounding drift. DecimalField stores exact base-10 values.
    price = models.DecimalField(max_digits=12, decimal_places=2)
    rsi = models.FloatField(null=True, blank=True)
    macd = models.FloatField(null=True, blank=True)
    macd_signal = models.FloatField(null=True, blank=True)
    # `reason` is filled with a plain technical explanation now; Week 3's LLM
    # explainer will overwrite it with a richer, news-grounded narrative.
    reason = models.TextField(blank=True)
    # Meta-labeling gate score: P(this signal clears costs), from the model in
    # quant/04_meta_labeling. Null when the gate isn't in play (no model file,
    # HOLD signal, or scoring failed) — null means "unscored", never 0.
    ml_prob = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # WHY unique_together: at most one signal per stock per day. This makes
        # the daily Celery task IDEMPOTENT — re-running it updates today's row
        # instead of inserting a duplicate (see signals/tasks.py).
        unique_together = [["stock", "date"]]
        ordering = ["-date"]
        # WHY this composite index: the "latest signals" endpoint filters by
        # date and often by signal_type. An index on (-date, signal_type)
        # serves both the ordering and the filter in one structure.
        indexes = [models.Index(fields=["-date", "signal_type"])]

    def __str__(self) -> str:
        return f"{self.stock.symbol} {self.date} {self.signal_type}"
