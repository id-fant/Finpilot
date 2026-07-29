from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("portfolio", "0003_alter_journalentry_stage")]

    operations = [
        migrations.CreateModel(
            name="ActionReceipt",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("key", models.CharField(max_length=80, unique=True)),
                ("action", models.CharField(max_length=40)),
                ("status", models.CharField(default="accepted", max_length=24)),
                ("response", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
