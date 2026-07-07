# YHARD2 — journal des actions IA confirmées + rollback (AgentActionLog).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0014_customuser_account_lockout"),
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentActionLog",
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
                ("action_key", models.CharField(max_length=100, verbose_name="Clé de l'action")),
                (
                    "risk_level",
                    models.CharField(
                        choices=[
                            ("internal", "Interne"),
                            ("outward", "Effet externe"),
                            ("irreversible", "Irréversible"),
                        ],
                        max_length=20,
                        verbose_name="Niveau de risque",
                    ),
                ),
                (
                    "proposal_hash",
                    models.CharField(
                        blank=True, default="", max_length=128,
                        verbose_name="Empreinte de la proposition",
                    ),
                ),
                (
                    "inputs_json",
                    models.JSONField(blank=True, default=dict, verbose_name="Paramètres"),
                ),
                ("proposed_at", models.DateTimeField(blank=True, null=True, verbose_name="Proposée le")),
                ("confirmed_at", models.DateTimeField(auto_now_add=True, verbose_name="Confirmée le")),
                ("executed_at", models.DateTimeField(blank=True, null=True, verbose_name="Exécutée le")),
                ("object_id", models.CharField(blank=True, default="", max_length=64)),
                ("object_repr", models.CharField(blank=True, default="", max_length=255)),
                ("undone_at", models.DateTimeField(blank=True, null=True, verbose_name="Annulée le")),
                ("undo_detail", models.TextField(blank=True, default="", verbose_name="Détail annulation")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_action_logs",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="agent_action_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Action IA confirmée",
                "verbose_name_plural": "Actions IA confirmées",
                "ordering": ["-confirmed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="agentactionlog",
            index=models.Index(fields=["company", "-confirmed_at"], name="agent_agent_company_c9d486_idx"),
        ),
        migrations.AddIndex(
            model_name="agentactionlog",
            index=models.Index(fields=["company", "action_key"], name="agent_agent_company_488c91_idx"),
        ),
        migrations.AddIndex(
            model_name="agentactionlog",
            index=models.Index(fields=["content_type", "object_id"], name="agent_agent_content_ef4139_idx"),
        ),
    ]
