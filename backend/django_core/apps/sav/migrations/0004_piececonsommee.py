# N46 — pièces consommées sur un ticket SAV (affichées sur le rapport, jamais
# de prix d'achat côté client ; stock optionnellement décrémenté). Additif.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("stock", "0001_initial"),
        ("sav", "0003_alter_ticket_installation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PieceConsommee",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "quantite",
                    models.DecimalField(
                        decimal_places=2, default=1, max_digits=10
                    ),
                ),
                ("stock_decremente", models.BooleanField(default=False)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pieces_sav",
                        to="authentication.company",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "produit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="pieces_sav",
                        to="stock.produit",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pieces",
                        to="sav.ticket",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pièce consommée",
                "verbose_name_plural": "Pièces consommées",
                "ordering": ["id"],
            },
        ),
    ]
