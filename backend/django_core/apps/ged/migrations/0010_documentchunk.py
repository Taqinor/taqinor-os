# FG352 — RAG / DocQA : fragments de documents indexés (pgvector, no-op sans clé)

import django.db.models.deletion
import pgvector.django.vector
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("ged", "0009_document_locked_by_locked_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentChunk",
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
                ("chunk_index", models.PositiveIntegerField(default=0)),
                ("texte", models.TextField(blank=True, default="")),
                (
                    "embedding",
                    pgvector.django.vector.VectorField(
                        blank=True, dimensions=1024, null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_document_chunks",
                        to="authentication.company",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="ged.document",
                    ),
                ),
            ],
            options={
                "verbose_name": "Fragment de document",
                "verbose_name_plural": "Fragments de document",
                "ordering": ["document", "chunk_index", "id"],
                "unique_together": {("document", "chunk_index")},
            },
        ),
        migrations.AddIndex(
            model_name="documentchunk",
            index=models.Index(
                fields=["company", "document"], name="ged_chunk_co_doc_idx"
            ),
        ),
    ]
