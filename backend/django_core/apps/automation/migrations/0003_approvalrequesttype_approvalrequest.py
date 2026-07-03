# Generated for XKB2 — types de demandes d'approbation ad-hoc configurables.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0010_customuser_supervisor"),
        ("automation", "0002_modelemessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovalRequestType",
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
                ("nom", models.CharField(max_length=120)),
                (
                    "description",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("champs_requis", models.JSONField(blank=True, default=list)),
                ("champs_optionnels", models.JSONField(blank=True, default=list)),
                (
                    "palier_approbateur",
                    models.CharField(
                        choices=[
                            ("responsable", "Responsable (ou plus)"),
                            ("admin", "Administrateur uniquement"),
                        ],
                        default="admin",
                        max_length=20,
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_request_types",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Type de demande d'approbation",
                "verbose_name_plural": "Types de demande d'approbation",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.CreateModel(
            name="ApprovalRequest",
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
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("approved", "Approuvé"),
                            ("rejected", "Rejeté"),
                        ],
                        default="pending",
                        max_length=12,
                    ),
                ),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "decision_note",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval_requests",
                        to="authentication.company",
                    ),
                ),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_requests_decidees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "demandeur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approval_requests_soumises",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "request_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requests",
                        to="automation.approvalrequesttype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Demande d'approbation",
                "verbose_name_plural": "Demandes d'approbation",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="approvalrequesttype",
            index=models.Index(
                fields=["company", "enabled"],
                name="automation_artype_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="approvalrequest",
            index=models.Index(
                fields=["company", "status"],
                name="automation_arequest_idx",
            ),
        ),
    ]
