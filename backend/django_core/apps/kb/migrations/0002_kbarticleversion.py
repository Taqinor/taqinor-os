# Generated for KB2 — versionnage des articles.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("kb", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbArticleVersion",
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
                    "version",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Numéro de version"
                    ),
                ),
                ("titre", models.CharField(max_length=255, verbose_name="Titre")),
                (
                    "contenu",
                    models.TextField(blank=True, default="", verbose_name="Contenu"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
                (
                    "auteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="kb_app_article_versions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_article_versions",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Version d’article",
                "verbose_name_plural": "Versions d’article",
                "ordering": ["-version", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="kbarticleversion",
            index=models.Index(
                fields=["company", "article"], name="kb_kbarticl_company_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="kbarticleversion",
            index=models.Index(
                fields=["article", "version"], name="kb_kbarticl_article_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="kbarticleversion",
            unique_together={("article", "version")},
        ),
    ]
