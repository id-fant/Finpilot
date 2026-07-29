from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("signals", "0002_signal_ml_prob")]

    operations = [
        migrations.AddField(
            model_name="signal",
            name="annualized_vol",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="signal",
            name="trend_regime",
            field=models.CharField(default="unknown", max_length=12),
        ),
    ]
