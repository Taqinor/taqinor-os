# Generated for FLOTTE17 — Garage + OrdreReparation (ordres de réparation,
# atelier/garage + coûts).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0014_echeanceentretien"),
    ]

    operations = [
        migrations.CreateModel(
            name="Garage",
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
                    "nom",
                    models.CharField(
                        max_length=120, verbose_name="Nom du garage"
                    ),
                ),
                (
                    "adresse",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="Adresse"
                    ),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="Téléphone"
                    ),
                ),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_garages",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Garage / atelier",
                "verbose_name_plural": "Garages / ateliers",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="OrdreReparation",
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
                    "description",
                    models.TextField(
                        blank=True, verbose_name="Description des travaux"
                    ),
                ),
                (
                    "date_ouverture",
                    models.DateField(verbose_name="Date d'ouverture"),
                ),
                (
                    "date_cloture",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de clôture"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("ouvert", "Ouvert"),
                            ("en_cours", "En cours"),
                            ("cloture", "Clôturé"),
                        ],
                        default="ouvert",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "cout_main_oeuvre",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Coût main d'œuvre (MAD)",
                    ),
                ),
                (
                    "cout_pieces",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Coût pièces (MAD)",
                    ),
                ),
                (
                    "cout_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Coût total (MAD)",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_ordres_reparation",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_ordres_reparation",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "garage",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_ordres_reparation",
                        to="flotte.garage",
                        verbose_name="Garage / atelier",
                    ),
                ),
                (
                    "echeance",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_ordres_reparation",
                        to="flotte.echeanceentretien",
                        verbose_name="Échéance d'entretien liée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ordre de réparation",
                "verbose_name_plural": "Ordres de réparation",
                "ordering": ["-date_ouverture", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="garage",
            index=models.Index(
                fields=["company", "actif"],
                name="flotte_garage_co_act_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ordrereparation",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_or_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ordrereparation",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_or_co_act_idx",
            ),
        ),
    ]
