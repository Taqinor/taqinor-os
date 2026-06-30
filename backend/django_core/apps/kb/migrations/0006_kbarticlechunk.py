# KB6 — Source de contenu pour le RAG/DocQA (FG352) : fragments d'articles
# indexés dans le MÊME magasin pgvector que la GED (no-op sans clé d'embedding).
# Entièrement additive (une nouvelle table), réversible par ``git revert`` /
# ``migrate kb 0005``. ``pgvector`` est déjà une dépendance dure (utilisée par la
# GED) : aucune nouvelle dépendance. Index nommé EXPLICITEMENT (≤30 car.) pour
# éviter toute divergence avec le nom haché déterministe de Django.
import django.db.models.deletion
import pgvector.django.vector
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("kb", "0005_kbarticleacl_kblecture"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbArticleChunk",
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
                    "chunk_index",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Position du fragment"
                    ),
                ),
                (
                    "texte",
                    models.TextField(blank=True, default="", verbose_name="Texte"),
                ),
                (
                    "embedding",
                    pgvector.django.vector.VectorField(
                        blank=True,
                        dimensions=1024,
                        null=True,
                        verbose_name="Embedding",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_article_chunks",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
            ],
            options={
                "verbose_name": "Fragment d'article",
                "verbose_name_plural": "Fragments d'article",
                "ordering": ["article", "chunk_index", "id"],
                "unique_together": {("article", "chunk_index")},
            },
        ),
        migrations.AddIndex(
            model_name="kbarticlechunk",
            index=models.Index(
                fields=["company", "article"], name="kb_chunk_co_article_idx"
            ),
        ),
    ]
