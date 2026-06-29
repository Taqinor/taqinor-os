# Generated for FLOTTE16 — EcheanceEntretien (échéances d'entretien dues).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0013_planentretien"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheanceEntretien",
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
                    "due_le",
                    models.DateField(
                        blank=True, null=True, verbose_name="Échéance (date)"
                    ),
                ),
                (
                    "due_km",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Échéance (km)"
                    ),
                ),
                (
                    "due_heures",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="Échéance (heures)",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_faire", "À faire"),
                            ("planifie", "Planifié"),
                            ("fait", "Fait"),
                        ],
                        default="a_faire",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                (
                    "genere_le",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Généré le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="echeances_entretien_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="echeances_entretien_flotte",
                        to="flotte.planentretien",
                        verbose_name="Plan d'entretien",
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="echeances_entretien_flotte",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Échéance d'entretien",
                "verbose_name_plural": "Échéances d'entretien",
                "ordering": ["statut", "due_le", "due_km", "due_heures", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="echeanceentretien",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_ech_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="echeanceentretien",
            index=models.Index(
                fields=["plan", "statut"],
                name="flotte_ech_plan_stat_idx",
            ),
        ),
    ]
