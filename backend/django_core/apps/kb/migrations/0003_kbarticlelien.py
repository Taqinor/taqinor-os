import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("kb", "0002_kbarticleversion"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbArticleLien",
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
                    "type_cible",
                    models.CharField(
                        choices=[
                            ("produit", "Produit"),
                            ("equipement", "Équipement"),
                            ("type_intervention", "Type d'intervention"),
                        ],
                        max_length=20,
                        verbose_name="Type de cible",
                    ),
                ),
                (
                    "cible_id",
                    models.PositiveIntegerField(verbose_name="ID de la cible"),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_app_article_liens",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liens",
                        to="kb.kbarticle",
                        verbose_name="Article",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lien de l'article",
                "verbose_name_plural": "Liens de l'article",
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="kbarticlelien",
            index=models.Index(
                fields=["company", "type_cible", "cible_id"],
                name="kb_kbarticl_company_a1b2c3_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="kbarticlelien",
            unique_together={("article", "type_cible", "cible_id")},
        ),
    ]
