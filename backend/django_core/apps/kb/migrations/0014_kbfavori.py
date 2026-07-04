# XKB15 — Favoris & récents KB. ``KbFavori`` : article étoilé par utilisateur
# (togglable, strictement personnel). Les « récents » réutilisent le
# ``KbLecture.lu_le`` déjà existant (KB7) — aucun nouveau modèle requis pour
# ça. Entièrement additive (une nouvelle table), réversible par
# ``git revert`` / ``migrate kb 0013``. Index nommé EXPLICITEMENT (≤30 car.)
# pour éviter toute divergence avec le nom haché déterministe de Django.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("kb", "0013_kbarticle_verification_verrou"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbFavori",
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
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Ajouté le"
                    ),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="favoris",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_favoris",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_favoris",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Favori",
                "verbose_name_plural": "Favoris",
                "ordering": ["-date_creation", "-id"],
                "unique_together": {("article", "utilisateur")},
            },
        ),
        migrations.AddIndex(
            model_name="kbfavori",
            index=models.Index(
                fields=["company", "utilisateur"], name="kb_favori_co_user_idx"
            ),
        ),
    ]
