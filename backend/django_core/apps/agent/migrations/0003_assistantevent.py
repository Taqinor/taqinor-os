# AIC6 — journal de l'assistant des commerciaux (contrat AIC1). Additive.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0002_alter_agentactionlog_action_key_and_more"),
        ("authentication", "0014_customuser_account_lockout"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("intention", models.CharField(choices=[("question_manuel", "Question sur le manuel"), ("donnee", "Donnée"), ("action", "Action"), ("bug", "Bug"), ("manque", "Fonction manquante"), ("hors_champ", "Hors champ")], default="donnee", max_length=20)),
                ("question", models.TextField(max_length=2000, verbose_name="Question")),
                ("resume_reponse", models.CharField(blank=True, default="", max_length=500, verbose_name="Résumé de la réponse")),
                ("ecran", models.CharField(blank=True, default="", max_length=255, verbose_name="Écran")),
                ("lead_id", models.PositiveIntegerField(blank=True, null=True, verbose_name="Lead")),
                ("outils_appeles", models.JSONField(blank=True, default=list, verbose_name="Outils appelés")),
                ("erreur", models.JSONField(blank=True, null=True, verbose_name="Erreur")),
                ("note", models.SmallIntegerField(choices=[(-1, "Pouce bas"), (0, "Pas encore noté"), (1, "Pouce haut")], default=0)),
                ("commentaire", models.CharField(blank=True, max_length=200, null=True)),
                ("modele", models.CharField(blank=True, default="", max_length=64, verbose_name="Modèle")),
                ("repli", models.BooleanField(default=False, verbose_name="Repli Groq")),
                ("manuel_present", models.BooleanField(default=False, verbose_name="Manuel présent")),
                ("tokens", models.JSONField(blank=True, default=dict, verbose_name="Tokens")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_set", to="authentication.company", verbose_name="Société")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assistant_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Événement de l'assistant",
                "verbose_name_plural": "Événements de l'assistant",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["company", "created_at"], name="agent_aev_company_created"),
                    models.Index(fields=["company", "intention"], name="agent_aev_company_intent"),
                ],
            },
        ),
    ]
