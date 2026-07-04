# XKB7 — Lecture obligatoire d'articles KB : assigne un article publié comme
# « à lire obligatoirement » à un utilisateur OU un palier de rôle. S'appuie
# sur le KbLecture/marquer-lu déjà existant (KB7) pour la complétion — cette
# table ne fait qu'ajouter l'assignation + l'échéance. Entièrement additive
# (une nouvelle table), réversible par ``git revert`` / ``migrate kb 0006``.
# Index nommé EXPLICITEMENT (≤30 car.) pour éviter toute divergence avec le
# nom haché déterministe de Django.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("kb", "0006_kbarticlechunk"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbLectureObligatoire",
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
                    "role_cible",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("admin", "Administrateur"),
                            ("responsable", "Responsable"),
                            ("normal", "Utilisateur"),
                        ],
                        default="",
                        max_length=20,
                        verbose_name="Palier de rôle ciblé",
                    ),
                ),
                (
                    "echeance",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Échéance"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Assigné le"
                    ),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lectures_obligatoires",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_lectures_obligatoires",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_lectures_obligatoires",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur assigné",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lecture obligatoire",
                "verbose_name_plural": "Lectures obligatoires",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="kblectureobligatoire",
            index=models.Index(
                fields=["company", "article"], name="kb_lecobl_co_article_idx"
            ),
        ),
    ]
