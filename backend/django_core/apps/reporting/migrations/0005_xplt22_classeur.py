# Generated for XPLT22 — lightweight embedded spreadsheet with live data (Classeur).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("reporting", "0004_xplt6_kpialerte"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Classeur",
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
                    "titre",
                    models.CharField(
                        default="Classeur sans titre", max_length=160
                    ),
                ),
                ("cellules", models.JSONField(blank=True, default=dict)),
                ("liens", models.JSONField(blank=True, default=dict)),
                ("partage", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_classeurs",
                        to="authentication.company",
                    ),
                ),
                (
                    "proprietaire",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_classeurs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Classeur",
                "verbose_name_plural": "Classeurs",
                "ordering": ["titre", "id"],
            },
        ),
        migrations.CreateModel(
            name="ClasseurPartageInterne",
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
                ("role", models.CharField(blank=True, default="", max_length=20)),
                (
                    "niveau",
                    models.CharField(
                        choices=[("lecture", "Lecture"), ("edition", "Édition")],
                        default="lecture",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "classeur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="partages_internes",
                        to="reporting.classeur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_classeur_partages_internes",
                        to="authentication.company",
                    ),
                ),
                (
                    "utilisateur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reporting_classeur_partages_recus",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Partage interne de classeur",
                "verbose_name_plural": "Partages internes de classeur",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="classeurpartageinterne",
            constraint=models.UniqueConstraint(
                condition=models.Q(("utilisateur__isnull", False)),
                fields=("classeur", "utilisateur"),
                name="rpt_classeur_partage_user_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="classeurpartageinterne",
            constraint=models.UniqueConstraint(
                condition=~models.Q(role=""),
                fields=("classeur", "role"),
                name="rpt_classeur_partage_role_uniq",
            ),
        ),
    ]
