# Generated for XPLT4 — webhook entrant générique alimentant une règle.

import django.db.models.deletion
from django.db import migrations, models

import apps.automation.models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("automation", "0004_approvaldelegation_decided_on_behalf_of"),
    ]

    operations = [
        migrations.CreateModel(
            name="IncomingWebhookTrigger",
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
                    "token",
                    models.CharField(
                        default=apps.automation.models._generate_webhook_token,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "hmac_secret",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_webhook_triggers",
                        to="authentication.company",
                    ),
                ),
                (
                    "rule",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_webhook",
                        to="automation.automationrule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Webhook entrant (automatisation)",
                "verbose_name_plural": "Webhooks entrants (automatisation)",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="incomingwebhooktrigger",
            index=models.Index(
                fields=["token"],
                name="automation_hook_token_idx",
            ),
        ),
    ]
