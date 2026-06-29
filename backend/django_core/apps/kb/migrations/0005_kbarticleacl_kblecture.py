# Migration additive KB7 : droits d'accès par rôle (KbArticleAcl) + suivi de
# lecture (KbLecture). Entièrement additive (deux nouvelles tables), réversible
# par ``git revert`` / ``migrate kb 0004``. Index nommés EXPLICITEMENT (≤30 car.)
# pour éviter toute divergence avec les noms hachés déterministes de Django.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("kb", "0004_rename_kb_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbArticleAcl",
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
                    "role",
                    models.CharField(
                        choices=[
                            ("admin", "Administrateur"),
                            ("responsable", "Responsable"),
                            ("normal", "Utilisateur"),
                        ],
                        max_length=20,
                        verbose_name="Palier de rôle autorisé",
                    ),
                ),
                (
                    "niveau",
                    models.CharField(
                        choices=[
                            ("lecture", "Lecture"),
                            ("edition", "Édition"),
                        ],
                        default="lecture",
                        max_length=10,
                        verbose_name="Niveau",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_acls",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="acls",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
            ],
            options={
                "verbose_name": "Droit d'accès de l'article",
                "verbose_name_plural": "Droits d'accès de l'article",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="KbLecture",
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
                    "lu_le",
                    models.DateTimeField(auto_now=True, verbose_name="Lu le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_lectures",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lectures",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_lectures",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Lecteur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lecture d'article",
                "verbose_name_plural": "Lectures d'article",
                "ordering": ["-lu_le", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="kbarticleacl",
            index=models.Index(
                fields=["company", "article"],
                name="kb_acl_company_article_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="kbarticleacl",
            unique_together={("article", "role", "niveau")},
        ),
        migrations.AddIndex(
            model_name="kblecture",
            index=models.Index(
                fields=["company", "article"],
                name="kb_lecture_company_art_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="kblecture",
            unique_together={("article", "utilisateur")},
        ),
    ]
