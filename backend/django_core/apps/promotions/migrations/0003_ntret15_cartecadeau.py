# NTRET15 — Cartes cadeaux (émission, solde, expiration, utilisation
# multi-passage). Nouveau modèle additif, ne touche aucune table existante.
from django.db import migrations, models

import apps.promotions.models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("promotions", "0002_ntret13_coupons"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarteCadeau",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(
                    default=apps.promotions.models.default_carte_cadeau_code,
                    max_length=32)),
                ("montant_initial", models.DecimalField(decimal_places=2, max_digits=12)),
                ("solde", models.DecimalField(decimal_places=2, max_digits=12)),
                ("date_emission", models.DateTimeField(auto_now_add=True)),
                ("date_expiration", models.DateField(
                    blank=True, null=True,
                    help_text="Vide = aucune expiration.")),
                ("statut", models.CharField(choices=[
                    ("active", "Active"),
                    ("epuisee", "Épuisée"),
                    ("expiree", "Expirée"),
                ], default="active", max_length=10)),
                ("company", models.ForeignKey(
                    on_delete=models.CASCADE,
                    related_name="cartes_cadeaux", to="authentication.company")),
            ],
            options={
                "verbose_name": "Carte cadeau",
                "verbose_name_plural": "Cartes cadeaux",
                "unique_together": {("company", "code")},
            },
        ),
    ]
