# ZCTR3 — Référentiel éditable des motifs de résiliation (close reasons) +
# branchement churn. Nouveau modèle `MotifResiliation` (company-scoped) +
# FK nullable `Resiliation.motif_ref`. Purement additif : le champ texte
# libre `Resiliation.motif` reste inchangé, `motif_ref` est optionnel.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
        ("contrats", "0034_zctr1_plan_recurrent"),
    ]

    operations = [
        migrations.CreateModel(
            name="MotifResiliation",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="Code")),
                ("libelle", models.CharField(
                    max_length=150, verbose_name="Libellé")),
                ("ordre", models.PositiveIntegerField(
                    default=0, verbose_name="Ordre")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("categorie", models.CharField(
                    blank=True,
                    choices=[
                        ("prix", "Prix"),
                        ("concurrent", "Concurrent"),
                        ("insatisfaction", "Insatisfaction"),
                        ("fin_projet", "Fin de projet"),
                        ("autre", "Autre"),
                    ],
                    default="", max_length=20, verbose_name="Catégorie")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="motifs_resiliation",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Motif de résiliation",
                "verbose_name_plural": "Motifs de résiliation",
                "ordering": ["ordre", "libelle", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="motifresiliation",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="contrats_motifresil_co_code"),
        ),
        migrations.AddIndex(
            model_name="motifresiliation",
            index=models.Index(
                fields=["company", "actif"],
                name="contrats_motifresil_co_act"),
        ),
        migrations.AddField(
            model_name="resiliation",
            name="motif_ref",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="resiliations",
                to="contrats.motifresiliation",
                verbose_name="Motif (référentiel)"),
        ),
    ]
