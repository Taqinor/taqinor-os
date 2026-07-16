import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0009_creativeasset"),
    ]

    operations = [
        migrations.CreateModel(
            name="CreativePolicy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "forbidden_rules",
                    models.JSONField(
                        blank=True, default=list,
                        verbose_name="Règles interdites"),
                ),
                (
                    "allowed_rules",
                    models.JSONField(
                        blank=True, default=list,
                        verbose_name="Règles permises"),
                ),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adsengine_creative_policy",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Policy créative",
                "verbose_name_plural": "Policies créatives",
                "ordering": ["-created_at"],
            },
        ),
    ]
