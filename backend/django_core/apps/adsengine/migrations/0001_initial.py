import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetaConnection",
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
                    "enabled",
                    models.BooleanField(
                        default=False, verbose_name="Connexion activée"),
                ),
                (
                    "ad_account_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID compte publicitaire"),
                ),
                (
                    "page_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID Page"),
                ),
                (
                    "pixel_id",
                    models.CharField(
                        blank=True, default="", max_length=64,
                        verbose_name="ID Pixel"),
                ),
                (
                    "credentials",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Identifiants (write-only)"),
                ),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adsengine_meta_connection",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Connexion Meta",
                "verbose_name_plural": "Connexions Meta",
                "ordering": ["-created_at"],
            },
        ),
    ]
