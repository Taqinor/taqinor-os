# Generated for XQHS4 — Catalogue de codes de défauts + Pareto qualité.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0030_xqhs3_controle_reception"),
    ]

    operations = [
        migrations.CreateModel(
            name="CodeDefaut",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("code", models.CharField(max_length=30, verbose_name="Code")),
                ("libelle", models.CharField(
                    max_length=255, verbose_name="Libellé")),
                ("famille", models.CharField(
                    choices=[
                        ("produit", "Produit"),
                        ("pose_dc", "Pose DC"),
                        ("pose_ac", "Pose AC"),
                        ("structure", "Structure"),
                        ("document", "Document"),
                        ("fournisseur", "Fournisseur"),
                        ("autre", "Autre"),
                    ],
                    default="autre", max_length=15, verbose_name="Famille")),
                ("actif", models.BooleanField(
                    default=True, verbose_name="Actif")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="qhse_codes_defaut",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Code de défaut",
                "verbose_name_plural": "Codes de défaut",
                "ordering": ["famille", "code"],
            },
        ),
        migrations.AddIndex(
            model_name="codedefaut",
            index=models.Index(
                fields=["company", "famille"],
                name="qhse_codedefaut_co_famille"),
        ),
        migrations.AddConstraint(
            model_name="codedefaut",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="qhse_codedefaut_co_code_uniq"),
        ),
        migrations.AddField(
            model_name="nonconformite",
            name="code_defaut",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="non_conformites", to="qhse.codedefaut",
                verbose_name="Code de défaut"),
        ),
        migrations.AddField(
            model_name="relevecontrole",
            name="code_defaut",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="releves_controle", to="qhse.codedefaut",
                verbose_name="Code de défaut"),
        ),
        migrations.AddField(
            model_name="incident",
            name="code_defaut",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="incidents", to="qhse.codedefaut",
                verbose_name="Code de défaut"),
        ),
    ]
