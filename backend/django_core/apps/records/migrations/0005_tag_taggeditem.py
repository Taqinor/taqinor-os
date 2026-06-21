# Generated manually for FG9 — records.Tag + records.TaggedItem (shared tag taxonomy)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0004_comment"),
        ("authentication", "0003_company_alter_customuser_groups_and_more"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
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
                ("nom", models.CharField(max_length=80)),
                ("couleur", models.CharField(blank=True, default="", max_length=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tags",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tag",
                "verbose_name_plural": "Tags",
                "ordering": ["nom"],
            },
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(
                fields=["company", "nom"],
                name="records_tag_company_nom_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="tag",
            index=models.Index(
                fields=["company", "nom"],
                name="records_tag_company_b0a4c2_idx",
            ),
        ),
        migrations.CreateModel(
            name="TaggedItem",
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
                ("object_id", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tagged_items",
                        to="records.tag",
                    ),
                ),
            ],
            options={
                "verbose_name": "Tag appliqué",
                "verbose_name_plural": "Tags appliqués",
                "ordering": ["tag__nom"],
            },
        ),
        migrations.AddConstraint(
            model_name="taggeditem",
            constraint=models.UniqueConstraint(
                fields=["tag", "content_type", "object_id"],
                name="records_taggeditem_tag_ct_obj_uniq",
            ),
        ),
        migrations.AddIndex(
            model_name="taggeditem",
            index=models.Index(
                fields=["content_type", "object_id"],
                name="records_tag_content_6d7bd1_idx",
            ),
        ),
    ]
