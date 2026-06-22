# Generated for PROJ4 — phases de projet (WBS), additif et revertable.
#
# Ajoute le modèle ``PhaseProjet`` (décomposition étude/appro/pose/MES/réception
# d'un projet). Pur ``CreateModel`` additif : aucun piège AddField(unique,
# default). Reversible par ``migrate gestion_projet 0003``.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("gestion_projet", "0003_projet_statut_machine"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhaseProjet",
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
                    "type_phase",
                    models.CharField(
                        choices=[
                            ("etude", "Étude"),
                            ("appro", "Approvisionnement"),
                            ("pose", "Pose"),
                            ("mes", "Mise en service"),
                            ("reception", "Réception"),
                        ],
                        max_length=12,
                        verbose_name="Type de phase",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Ordre"
                    ),
                ),
                (
                    "date_debut_prevue",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de début prévue",
                    ),
                ),
                (
                    "date_fin_prevue",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de fin prévue",
                    ),
                ),
                (
                    "date_debut_reelle",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de début réelle",
                    ),
                ),
                (
                    "date_fin_reelle",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de fin réelle",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_venir", "À venir"),
                            ("en_cours", "En cours"),
                            ("terminee", "Terminée"),
                        ],
                        default="a_venir",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "avancement_pct",
                    models.PositiveSmallIntegerField(
                        default=0,
                        validators=[
                            django.core.validators.MaxValueValidator(100)
                        ],
                        verbose_name="Avancement (%)",
                    ),
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
                        related_name="projet_phases",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "projet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="phases",
                        to="gestion_projet.projet",
                        verbose_name="Projet",
                    ),
                ),
            ],
            options={
                "verbose_name": "Phase de projet",
                "verbose_name_plural": "Phases de projet",
                "ordering": ["projet", "ordre", "id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="phaseprojet",
            unique_together={("projet", "type_phase")},
        ),
    ]
