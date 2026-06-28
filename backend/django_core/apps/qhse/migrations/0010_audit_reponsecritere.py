# Generated for QHSE16 — Audit + ReponseCritere

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0009_grilleaudit_critereaudit"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Audit",
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
                    "date_audit",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de l'audit"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("en_cours", "En cours"),
                            ("clos", "Clôturé"),
                        ],
                        default="brouillon",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        verbose_name="Score (%)",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du chantier"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "auditeur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_audits_conduits",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auditeur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_audits",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "grille",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="qhse_audits",
                        to="qhse.grilleaudit",
                        verbose_name="Grille d'audit",
                    ),
                ),
            ],
            options={
                "verbose_name": "Audit",
                "verbose_name_plural": "Audits",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="ReponseCritere",
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
                    "resultat",
                    models.CharField(
                        choices=[
                            ("conforme", "Conforme"),
                            ("non_conforme", "Non conforme"),
                            ("na", "Non applicable"),
                        ],
                        default="na",
                        max_length=12,
                        verbose_name="Résultat",
                    ),
                ),
                (
                    "note",
                    models.TextField(
                        blank=True, default="", verbose_name="Note / observation"
                    ),
                ),
                (
                    "ncr_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID de la non-conformité levée",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "audit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_reponses",
                        to="qhse.audit",
                        verbose_name="Audit",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_reponses_critere",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "critere",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="qhse_reponses",
                        to="qhse.critereaudit",
                        verbose_name="Critère d'audit",
                    ),
                ),
            ],
            options={
                "verbose_name": "Réponse à critère",
                "verbose_name_plural": "Réponses à critères",
                "ordering": ["audit", "critere__ordre", "critere__id"],
            },
        ),
        migrations.AddConstraint(
            model_name="reponsecritere",
            constraint=models.UniqueConstraint(
                fields=["audit", "critere"],
                name="qhse_reponsecritere_audit_critere_uniq",
            ),
        ),
    ]
