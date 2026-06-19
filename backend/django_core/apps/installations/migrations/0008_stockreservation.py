# Generated for N14 — réservation de stock sur chantier puis consommation à
# « Installé ». Entièrement additif (nouveau modèle, aucune table existante
# modifiée).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("installations", "0007_alter_intervention_options_intervention_camionnette_and_more"),
        ("stock", "0019_retourfournisseur_ligneretourfournisseur"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockReservation",
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
                ("quantite", models.PositiveIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("consomme", models.BooleanField(default=False)),
                ("date_consommation", models.DateTimeField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_reservations",
                        to="authentication.company",
                    ),
                ),
                (
                    "installation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to="installations.installation",
                    ),
                ),
                (
                    "produit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to="stock.produit",
                    ),
                ),
            ],
            options={
                "verbose_name": "Réservation de stock",
                "verbose_name_plural": "Réservations de stock",
                "ordering": ["installation_id", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="stockreservation",
            index=models.Index(
                fields=["produit", "active", "consomme"],
                name="installatio_produit_a569bc_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="stockreservation",
            unique_together={("installation", "produit")},
        ),
    ]
