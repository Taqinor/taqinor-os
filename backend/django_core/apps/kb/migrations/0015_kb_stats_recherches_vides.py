# XKB16 — Statistiques KB & recherches infructueuses.
# ``KbArticle.vues`` (compteur, défaut 0 — RÉTRO-COMPATIBLE) + ``KbRechercheVide``
# (journal des recherches sans résultat, nouvelle table). Entièrement additive,
# réversible par ``git revert`` / ``migrate kb 0014``. Index nommé
# EXPLICITEMENT (≤30 car.) pour éviter toute divergence avec le nom haché
# déterministe de Django.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("kb", "0014_kbfavori"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="vues",
            field=models.PositiveIntegerField(default=0, verbose_name="Vues"),
        ),
        migrations.CreateModel(
            name="KbRechercheVide",
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
                    "terme",
                    models.CharField(
                        max_length=255, verbose_name="Terme recherché"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Recherché le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_recherches_vides",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="kb_app_recherches_vides",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Recherche sans résultat",
                "verbose_name_plural": "Recherches sans résultat",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="kbrecherchevide",
            index=models.Index(
                fields=["company", "terme"], name="kb_rech_vide_co_terme_idx"
            ),
        ),
    ]
