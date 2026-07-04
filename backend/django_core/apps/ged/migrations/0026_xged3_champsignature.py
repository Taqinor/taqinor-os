# XGED3 — Zones de champs positionnées sur le PDF à signer (modèles de
# signature).
#
# Migration strictement ADDITIVE (réversible) : crée `ChampSignature`, une
# zone de champ (signature/initiales/date/texte/case) positionnée en
# POURCENTAGE de page sur une demande de signature EN COURS ou un
# `ModeleDocument` (GED27) réutilisable. Aucune table existante n'est
# retirée ni renommée.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("ged", "0025_xged2_multi_signataires"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChampSignature",
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
                    "type_champ",
                    models.CharField(
                        choices=[
                            ("signature", "Signature"),
                            ("initiales", "Initiales"),
                            ("date", "Date"),
                            ("texte", "Texte"),
                            ("case", "Case à cocher"),
                        ],
                        default="signature",
                        max_length=12,
                        verbose_name="type de champ",
                    ),
                ),
                (
                    "page",
                    models.PositiveIntegerField(
                        default=0, verbose_name="page (0-based)"
                    ),
                ),
                ("x", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("y", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                (
                    "largeur",
                    models.DecimalField(decimal_places=2, default=20, max_digits=5),
                ),
                (
                    "hauteur",
                    models.DecimalField(decimal_places=2, default=5, max_digits=5),
                ),
                (
                    "role",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                ("requis", models.BooleanField(default=True, verbose_name="requis")),
                (
                    "valeur",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ged_champs_signature",
                        to="authentication.company",
                    ),
                ),
                (
                    "demande",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="champs",
                        to="ged.demandesignaturedocument",
                    ),
                ),
                (
                    "modele",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="champs_signature",
                        to="ged.modeledocument",
                    ),
                ),
            ],
            options={
                "verbose_name": "Champ de signature",
                "verbose_name_plural": "Champs de signature",
                "ordering": ["page", "y", "x", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="champsignature",
            index=models.Index(
                fields=["company", "demande"], name="ged_champ_co_demande_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="champsignature",
            index=models.Index(
                fields=["company", "modele"], name="ged_champ_co_modele_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="champsignature",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("demande__isnull", False), ("modele__isnull", True))
                    | models.Q(("demande__isnull", True), ("modele__isnull", False))
                ),
                name="ged_champ_exactly_one_target",
            ),
        ),
    ]
