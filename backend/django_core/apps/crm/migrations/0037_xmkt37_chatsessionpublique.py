# XMKT37 — Livechat / assistant IA de qualification (ERP-side) : nouveau
# modèle additif ChatSessionPublique. Aucune modification d'un modèle
# existant.

import django.db.models.deletion
from django.db import migrations, models

import apps.crm.models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0005_alter_customuser_role"),
        ("crm", "0036_xmkt32_lead_source_meta_lead_ads"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatSessionPublique",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("token", models.CharField(
                    default=apps.crm.models._default_chat_token,
                    editable=False, max_length=64, unique=True)),
                ("transcript", models.JSONField(blank=True, default=list)),
                ("statut", models.CharField(
                    choices=[
                        ("active", "Active"),
                        ("qualifiee", "Qualifiée"),
                        ("fermee", "Fermée"),
                    ],
                    default="active", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_message_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="chat_sessions_publiques",
                    to="authentication.company")),
                ("lead", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="chat_sessions_publiques", to="crm.lead")),
            ],
            options={
                "verbose_name": "Session livechat publique",
                "verbose_name_plural": "Sessions livechat publiques",
                "ordering": ["-last_message_at"],
            },
        ),
    ]
