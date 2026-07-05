# Generated manually — ZPAI9 : nouveau modèle TypeEntreePonctuelle (catalogue
# company-scoped) + FK nullable ElementVariable.type_entree (NULL par défaut =
# comportement historique inchangé). Additif, aucune donnée existante touchée.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZPAI9 — TypeEntreePonctuelle + ElementVariable.type_entree (additif)."""

    dependencies = [
        ("paie", "0038_zpai8_rubrique_arrondi_absence"),
    ]

    operations = [
        migrations.CreateModel(
            name="TypeEntreePonctuelle",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("code", models.CharField(max_length=30, verbose_name="Code")),
                ("libelle", models.CharField(
                    max_length=120, verbose_name="Libellé")),
                ("sens", models.CharField(
                    choices=[("gain", "Gain"), ("retenue", "Retenue")],
                    default="gain", max_length=8, verbose_name="Sens")),
                ("imposable", models.BooleanField(
                    default=True, verbose_name="Imposable (IR)")),
                ("soumis_cnss", models.BooleanField(
                    default=True, verbose_name="Soumis CNSS")),
                ("soumis_amo", models.BooleanField(
                    default=True, verbose_name="Soumis AMO")),
                ("actif", models.BooleanField(default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="paie_types_entree_ponctuelle",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Type d'entrée ponctuelle",
                "verbose_name_plural": "Types d'entrée ponctuelle",
                "ordering": ["libelle", "code"],
                "unique_together": {("company", "code")},
            },
        ),
        migrations.AddField(
            model_name="elementvariable",
            name="type_entree",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="elements_variables",
                to="paie.typeentreeponctuelle",
                verbose_name="Type d'entrée ponctuelle (catalogue)"),
        ),
    ]
