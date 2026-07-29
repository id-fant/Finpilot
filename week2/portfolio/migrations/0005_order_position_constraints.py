from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0004_actionreceipt")]

    operations = [
        migrations.AddConstraint(
            model_name="position",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_open", True)),
                fields=("stock",),
                name="one_open_position_per_stock",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=models.Q(("signal__isnull", False)),
                fields=("signal", "side"),
                name="unique_order_signal_side",
            ),
        ),
    ]
