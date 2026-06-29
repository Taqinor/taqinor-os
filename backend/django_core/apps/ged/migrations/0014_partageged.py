# GED20 — Partage public d'un document par lien tokenisé (expiry/mdp/quota).
#
# Ajoute le modèle `PartageGed` : un lien PUBLIC (sans login) vers un document
# GED, authentifié par un seul secret (`token` long et imprévisible). Le partage
# peut porter une expiration (`expires_at`), un mot de passe optionnel
# (`password_hash`, haché — jamais en clair) et un quota de téléchargements
# (`quota_max`). `telechargements` compte les accès servis ; `actif` permet la
# révocation immédiate.
#
# Additive et réversible. SÉCURITÉ : l'endpoint public ne fait jamais confiance à
# une identité/société venue de la requête — tout est résolu DEPUIS le jeton (la
# société du document est implicite). Un lien révoqué/expiré/au quota épuisé
# renvoie 404/410 sans fuite. Company posée côté serveur (cohérente avec le
# document) — jamais lue du corps de requête.

import apps.ged.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ged", "0013_aclged"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartageGed",
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
                        default=apps.ged.models._default_partage_token,
                        editable=False,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="expire le"
                    ),
                ),
                (
                    "password_hash",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="hash du mot de passe",
                    ),
                ),
                (
                    "quota_max",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="quota de téléchargements",
                    ),
                ),
                (
                    "telechargements",
                    models.PositiveIntegerField(
                        default=0, verbose_name="téléchargements"
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="actif"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_partages",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="partages",
                        to="ged.document",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ged_partages_crees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Partage GED",
                "verbose_name_plural": "Partages GED",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="partageged",
            index=models.Index(
                fields=["company", "document"], name="ged_partage_co_doc_idx"
            ),
        ),
    ]
