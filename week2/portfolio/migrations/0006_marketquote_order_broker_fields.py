from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0005_order_position_constraints"),
        ("signals", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="broker_order_id",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="order",
            name="fill_applied",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="last_broker_update",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="MarketQuote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("instrument_token", models.BigIntegerField(unique=True)),
                ("last_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("exchange_timestamp", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now=True)),
                ("stock", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="market_quote", to="signals.stock")),
            ],
            options={"ordering": ["stock__symbol"]},
        ),
    ]
