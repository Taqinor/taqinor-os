import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("adsengine", "0003_mirrors_insightsnapshot"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EngineAction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("create_campaign", "Créer une campagne"),
                            ("create_adset", "Créer un ad set"),
                            ("create_ad", "Créer une ad"),
                        ],
                        max_length=32, verbose_name="Type"),
                ),
                (
                    "payload",
                    models.JSONField(
                        blank=True, default=dict,
                        verbose_name="Charge utile"),
                ),
                (
                    "reason_fr",
                    models.TextField(verbose_name="Raison (une phrase FR)"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("proposee", "Proposée"),
                            ("approuvee", "Approuvée"),
                            ("rejetee", "Rejetée"),
                            ("appliquee", "Appliquée"),
                            ("echouee", "Échouée"),
                        ],
                        default="proposee", max_length=12,
                        verbose_name="Statut"),
                ),
                (
                    "auto",
                    models.BooleanField(
                        default=False,
                        verbose_name="Jouée automatiquement (ENG8)"),
                ),
                (
                    "applied_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Appliquée le"),
                ),
                (
                    "result",
                    models.JSONField(
                        blank=True, default=dict, verbose_name="Résultat"),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True, default="", verbose_name="Erreur"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="adsengine_actions_approuvees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Approuvée / décidée par"),
                ),
            ],
            options={
                "verbose_name": "Action du moteur",
                "verbose_name_plural": "Actions du moteur",
                "ordering": ["-created_at"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("reason_fr", ""), _negated=True),
                        name="adseng_action_reason_req"),
                ],
            },
        ),
    ]
