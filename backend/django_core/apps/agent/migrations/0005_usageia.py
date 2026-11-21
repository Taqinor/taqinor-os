# Décision fondateur 21/11/2026 — journal d'usage IA persisté (UsageIA). Additive.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0004_agentactionlog_origine"),
        ("authentication", "0014_customuser_account_lockout"),
    ]

    operations = [
        migrations.CreateModel(
            name="UsageIA",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("capability", models.CharField(max_length=20, verbose_name="Capacité")),
                ("provider", models.CharField(max_length=40, verbose_name="Fournisseur")),
                ("feature_key", models.CharField(blank=True, default="", max_length=120,
                                                 verbose_name="Fonction appelante")),
                ("input_tokens", models.PositiveIntegerField(default=0, verbose_name="Jetons en entrée")),
                ("output_tokens", models.PositiveIntegerField(default=0, verbose_name="Jetons en sortie")),
                ("cout", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True,
                                             verbose_name="Coût estimé (MAD)")),
                ("success", models.BooleanField(default=True, verbose_name="Succès")),
                ("duration_ms", models.PositiveIntegerField(default=0, verbose_name="Durée (ms)")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="%(app_label)s_%(class)s_set",
                                              to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Usage IA",
                "verbose_name_plural": "Usages IA",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["company", "created_at"], name="agent_uia_company_created"),
                ],
            },
        ),
    ]
