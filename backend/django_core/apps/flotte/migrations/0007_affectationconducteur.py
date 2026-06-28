# Generated for FLOTTE8 — AffectationConducteur (conducteur ↔ véhicule datée).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("flotte", "0006_conducteur"),
    ]

    operations = [
        migrations.CreateModel(
            name="AffectationConducteur",
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
                    "date_debut",
                    models.DateField(verbose_name="Date de début"),
                ),
                (
                    "date_fin",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de fin"
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, verbose_name="Notes"),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
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
                        related_name="affectations_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "conducteur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affectations_flotte",
                        to="flotte.conducteur",
                        verbose_name="Conducteur",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="affectations_flotte",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Affectation conducteur",
                "verbose_name_plural": "Affectations conducteurs",
                "ordering": ["-date_debut"],
            },
        ),
        migrations.AddIndex(
            model_name="affectationconducteur",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_aff_co_veh_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="affectationconducteur",
            index=models.Index(
                fields=["company", "conducteur"],
                name="flotte_aff_co_cond_idx",
            ),
        ),
    ]
