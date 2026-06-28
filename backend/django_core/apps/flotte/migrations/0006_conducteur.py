# Generated for FLOTTE7 — Conducteur + permis (lien authentication.User).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("flotte", "0005_actifflotte"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Conducteur",
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
                    "nom",
                    models.CharField(max_length=120, verbose_name="Nom complet"),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="Téléphone"
                    ),
                ),
                (
                    "numero_permis",
                    models.CharField(
                        blank=True, max_length=50, verbose_name="Numéro de permis"
                    ),
                ),
                (
                    "categorie_permis",
                    models.CharField(
                        blank=True,
                        help_text="Ex. : B, C, CE, D…",
                        max_length=30,
                        verbose_name="Catégorie de permis",
                    ),
                ),
                (
                    "date_obtention",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date d'obtention du permis",
                    ),
                ),
                (
                    "date_expiration",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date d'expiration du permis",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conducteurs_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="conducteurs_flotte",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Utilisateur ERP",
                    ),
                ),
            ],
            options={
                "verbose_name": "Conducteur",
                "verbose_name_plural": "Conducteurs",
                "ordering": ["nom"],
            },
        ),
    ]
