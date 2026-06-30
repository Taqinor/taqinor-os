# Generated for QHSE31 — Analyse d'incident (arbre des causes) → CAPA.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("qhse", "0020_declarationcnss"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnalyseIncident",
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
                    "methode",
                    models.CharField(
                        choices=[
                            ("5m", "Cinq M (Ishikawa)"),
                            ("arbre_des_causes", "Arbre des causes"),
                            ("5pourquoi", "Cinq pourquoi"),
                        ],
                        default="arbre_des_causes",
                        max_length=20,
                        verbose_name="Méthode d'analyse",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, default="", verbose_name="Description"
                    ),
                ),
                (
                    "synthese",
                    models.TextField(
                        blank=True, default="", verbose_name="Synthèse"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_cours", "En cours"),
                            ("clos", "Clos"),
                        ],
                        default="en_cours",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_analyse",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de l'analyse"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "analyste",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_analyses_incident",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Analyste",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_analyses_incident",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "incident",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="analyse",
                        to="qhse.incident",
                        verbose_name="Incident",
                    ),
                ),
                (
                    "non_conformite",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="analyses_incident",
                        to="qhse.nonconformite",
                        verbose_name="Non-conformité liée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Analyse d'incident",
                "verbose_name_plural": "Analyses d'incident",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="CauseIncident",
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
                    "type_cause",
                    models.CharField(
                        choices=[
                            ("fait", "Fait"),
                            ("cause_immediate", "Cause immédiate"),
                            ("cause_profonde", "Cause profonde"),
                            ("cause_racine", "Cause racine"),
                        ],
                        default="fait",
                        max_length=20,
                        verbose_name="Type de cause",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(max_length=255, verbose_name="Libellé"),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "analyse",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="causes",
                        to="qhse.analyseincident",
                        verbose_name="Analyse",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_causes_incident",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="enfants",
                        to="qhse.causeincident",
                        verbose_name="Cause parente",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cause d'incident",
                "verbose_name_plural": "Causes d'incident",
                "ordering": ["ordre", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="analyseincident",
            index=models.Index(
                fields=["company", "statut"], name="qhse_analyse_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="causeincident",
            index=models.Index(
                fields=["analyse", "parent"], name="qhse_cause_analyse_par"
            ),
        ),
    ]
