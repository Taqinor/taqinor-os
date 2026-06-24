# Generated for FLOTTE5 — référence d'actif unifiée (Vehicule | EnginRoulant).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("flotte", "0004_referentielflotte"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActifFlotte",
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
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actifs_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "vehicule",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actif_flotte",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
                (
                    "engin",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actif_flotte",
                        to="flotte.enginroulant",
                        verbose_name="Engin roulant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Référence d'actif",
                "verbose_name_plural": "Références d'actif",
                "ordering": ["date_creation"],
            },
        ),
    ]
