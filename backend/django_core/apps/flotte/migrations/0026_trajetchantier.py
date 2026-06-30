# Generated for FLOTTE29 — journal kilométrique & trajets imputés chantier.
# Ajoute le modèle ``TrajetChantier`` : déplacement d'un ``ActifFlotte``
# (FLOTTE5, même app) imputé à un chantier (``installations.Installation``) par
# son id NUMÉRIQUE (jamais un FK cross-app dur). La validation « même société »
# du chantier se fait au sérialiseur via ``installations.selectors``. Additif,
# multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0025_trajettelematique"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrajetChantier",
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
                    "installation_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Chantier (id)"
                    ),
                ),
                (
                    "date_trajet",
                    models.DateField(verbose_name="Date du trajet"),
                ),
                (
                    "motif",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name="Motif / objet du trajet",
                    ),
                ),
                (
                    "km_depart",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Kilométrage de départ",
                    ),
                ),
                (
                    "km_arrivee",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Kilométrage d'arrivée",
                    ),
                ),
                (
                    "distance_km",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Distance parcourue (km)",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, verbose_name="Notes"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_trajets_chantier",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_trajets_chantier",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Trajet imputé chantier",
                "verbose_name_plural": "Trajets imputés chantier",
                "ordering": ["-date_trajet", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="trajetchantier",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_trch_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="trajetchantier",
            index=models.Index(
                fields=["company", "installation_id"],
                name="flotte_trch_co_inst_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="trajetchantier",
            index=models.Index(
                fields=["company", "date_trajet"],
                name="flotte_trch_co_date_idx",
            ),
        ),
    ]
