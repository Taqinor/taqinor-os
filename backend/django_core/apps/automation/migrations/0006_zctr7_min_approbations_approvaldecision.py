# Generated for ZCTR7 — options de catégorie d'approbation (min approbations,
# pièce jointe obligatoire, champs requis granulaires).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("automation", "0005_incomingwebhooktrigger"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequesttype",
            name="min_approbations",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="approvalrequesttype",
            name="piece_jointe_obligatoire",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="approvalrequesttype",
            name="champs_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="ApprovalDecision",
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
                    "decision",
                    models.CharField(
                        choices=[
                            ("approve", "Favorable"),
                            ("reject", "Défavorable"),
                        ],
                        max_length=10,
                    ),
                ),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "on_behalf_of",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_decisions_deleguees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="decisions",
                        to="automation.approvalrequest",
                    ),
                ),
            ],
            options={
                "verbose_name": "Décision d'approbation",
                "verbose_name_plural": "Décisions d'approbation",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="approvaldecision",
            index=models.Index(
                fields=["request", "decision"],
                name="automation_decision_idx",
            ),
        ),
    ]
