# Generated for FLOTTE15 — PlanEntretien (plans d'entretien préventif).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0012_cartecarburant"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanEntretien",
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
                    "type_entretien",
                    models.CharField(
                        max_length=60, verbose_name="Type d'entretien"
                    ),
                ),
                (
                    "intervalle_km",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Intervalle (km)"
                    ),
                ),
                (
                    "intervalle_jours",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Intervalle (jours)"
                    ),
                ),
                (
                    "intervalle_heures",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Intervalle (heures)",
                    ),
                ),
                (
                    "dernier_km",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Dernier entretien (km)",
                    ),
                ),
                (
                    "derniere_date",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Dernier entretien (date)",
                    ),
                ),
                (
                    "dernier_heures",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Dernier entretien (heures)",
                    ),
                ),
                (
                    "seuil_alerte_km",
                    models.PositiveIntegerField(
                        default=500, verbose_name="Marge d'alerte (km)"
                    ),
                ),
                (
                    "seuil_alerte_jours",
                    models.PositiveIntegerField(
                        default=14, verbose_name="Marge d'alerte (jours)"
                    ),
                ),
                (
                    "seuil_alerte_heures",
                    models.PositiveIntegerField(
                        default=25, verbose_name="Marge d'alerte (heures)"
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
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
                        related_name="plans_entretien_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="plans_entretien_flotte",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Plan d'entretien préventif",
                "verbose_name_plural": "Plans d'entretien préventif",
                "ordering": ["type_entretien"],
            },
        ),
        migrations.AddIndex(
            model_name="planentretien",
            index=models.Index(
                fields=["company", "actif"],
                name="flotte_plan_co_act_idx",
            ),
        ),
    ]
