# Generated manually — XPAI24 structures de paie par catégorie (modèles de
# rubriques appliqués en une fois au profil à la création).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """XPAI24 — Structures de paie (StructurePaie / StructurePaieRubrique)."""

    dependencies = [
        ("paie", "0028_xpai14_arret_cnss"),
    ]

    operations = [
        migrations.CreateModel(
            name="StructurePaie",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("code", models.CharField(max_length=30, verbose_name="Code")),
                ("libelle", models.CharField(max_length=120, verbose_name="Libellé")),
                ("description", models.CharField(
                    blank=True, default="", max_length=255,
                    verbose_name="Description")),
                ("actif", models.BooleanField(default=True, verbose_name="Active")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créée le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_structures",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Structure de paie",
                "verbose_name_plural": "Structures de paie",
                "ordering": ["libelle"],
                "unique_together": {("company", "code")},
            },
        ),
        migrations.CreateModel(
            name="StructurePaieRubrique",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("montant", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name="Montant (surcharge)")),
                ("taux", models.DecimalField(
                    blank=True, decimal_places=4, max_digits=8, null=True,
                    verbose_name="Taux % (surcharge)")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_structure_rubriques",
                    to="authentication.company", verbose_name="Société")),
                ("rubrique", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="structures_defaut",
                    to="paie.rubrique", verbose_name="Rubrique")),
                ("structure", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rubriques_defaut",
                    to="paie.structurepaie", verbose_name="Structure")),
            ],
            options={
                "verbose_name": "Rubrique de structure",
                "verbose_name_plural": "Rubriques de structure",
                "ordering": ["rubrique__ordre", "id"],
                "unique_together": {("structure", "rubrique")},
            },
        ),
        migrations.AddField(
            model_name="profilpaie",
            name="structure",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="profils", to="paie.structurepaie",
                verbose_name="Structure de paie appliquée"),
        ),
    ]
