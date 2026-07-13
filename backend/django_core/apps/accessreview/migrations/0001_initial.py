import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessReviewCampaign",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("nom", models.CharField(max_length=160, verbose_name="Nom")),
                (
                    "perimetre",
                    models.CharField(
                        choices=[("all", "Tous les comptes"),
                                 ("role", "Par rôle"),
                                 ("module", "Par module")],
                        default="all", max_length=10),
                ),
                ("perimetre_ref", models.CharField(
                    blank=True, default="", max_length=64)),
                ("date_debut", models.DateField(blank=True, null=True)),
                ("date_fin", models.DateField(blank=True, null=True)),
                (
                    "statut",
                    models.CharField(
                        choices=[("ouverte", "Ouverte"), ("close", "Close")],
                        default="ouverte", max_length=10),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Campagne de revue d'accès",
                "verbose_name_plural": "Campagnes de revue d'accès",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AccessReviewItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role_snapshot", models.JSONField(blank=True, default=dict)),
                (
                    "decision",
                    models.CharField(
                        choices=[("en_attente", "En attente"),
                                 ("maintenu", "Maintenu"),
                                 ("revoque", "Révoqué")],
                        default="en_attente", max_length=12),
                ),
                ("commentaire", models.TextField(blank=True, default="")),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
                (
                    "campagne",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="accessreview.accessreviewcampaign"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_review_items",
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    "reviewer",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="access_reviews_faites",
                        to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Item de revue d'accès",
                "verbose_name_plural": "Items de revue d'accès",
            },
        ),
        migrations.AddConstraint(
            model_name="accessreviewitem",
            constraint=models.UniqueConstraint(
                fields=("campagne", "user"),
                name="uniq_accessreview_item_par_campagne_user"),
        ),
    ]
