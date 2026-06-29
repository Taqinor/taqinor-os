# Generated for QHSE21 — Évaluation des risques (document unique) + lignes

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0013_retourclientqualite"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvaluationRisque",
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
                    "reference",
                    models.CharField(
                        blank=True, default="", max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "titre",
                    models.CharField(max_length=255, verbose_name="Titre"),
                ),
                (
                    "date_evaluation",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date d'évaluation",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("validee", "Validée"),
                            ("archivee", "Archivée"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du chantier",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"
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
                        related_name="qhse_evaluations_risque",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "evaluateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_evaluations_risque",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Évaluateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Évaluation des risques",
                "verbose_name_plural": "Évaluations des risques",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="LigneEvaluationRisque",
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
                    "poste",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Poste",
                    ),
                ),
                (
                    "activite",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Activité",
                    ),
                ),
                (
                    "danger",
                    models.CharField(
                        max_length=255, verbose_name="Danger / risque"
                    ),
                ),
                (
                    "gravite",
                    models.PositiveSmallIntegerField(
                        default=1, verbose_name="Gravité (1–5)"
                    ),
                ),
                (
                    "probabilite",
                    models.PositiveSmallIntegerField(
                        default=1, verbose_name="Probabilité (1–5)"
                    ),
                ),
                (
                    "criticite",
                    models.PositiveSmallIntegerField(
                        default=1,
                        verbose_name="Criticité (gravité × probabilité)",
                    ),
                ),
                (
                    "mesures_prevention",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="Mesures de prévention",
                    ),
                ),
                (
                    "risque_residuel",
                    models.TextField(
                        blank=True, default="",
                        verbose_name="Risque résiduel",
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Ordre"
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
                        related_name="qhse_lignes_evaluation_risque",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "evaluation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="qhse.evaluationrisque",
                        verbose_name="Évaluation des risques",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne d'évaluation des risques",
                "verbose_name_plural": "Lignes d'évaluation des risques",
                "ordering": ["evaluation", "ordre", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="evaluationrisque",
            constraint=models.UniqueConstraint(
                fields=["company", "reference"],
                name="qhse_evalrisque_co_ref_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="evaluationrisque",
            index=models.Index(
                fields=["company", "statut"],
                name="qhse_evalrisque_co_statut",
            ),
        ),
        migrations.AddIndex(
            model_name="evaluationrisque",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_evalrisque_co_chant",
            ),
        ),
        migrations.AddIndex(
            model_name="ligneevaluationrisque",
            index=models.Index(
                fields=["company", "evaluation"],
                name="qhse_ligneer_co_eval",
            ),
        ),
    ]
