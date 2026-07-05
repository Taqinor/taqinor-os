# Generated manually — ZRH15 lignes de parcours (timeline expérience/formation).
# Additif, deux nouveaux modèles.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """ZRH15 — TypeLigneParcours + LigneParcours (additif)."""

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("rh", "0077_zrh13_demande_allocation"),
    ]

    operations = [
        migrations.CreateModel(
            name="TypeLigneParcours",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("libelle", models.CharField(
                    max_length=80, verbose_name="Libellé")),
                ("ordre", models.PositiveIntegerField(
                    default=0, verbose_name="Ordre")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_types_ligne_parcours",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Type de ligne de parcours",
                "verbose_name_plural": "Types de ligne de parcours",
                "ordering": ["ordre", "libelle"],
            },
        ),
        migrations.CreateModel(
            name="LigneParcours",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("intitule", models.CharField(
                    max_length=160, verbose_name="Intitulé")),
                ("organisme", models.CharField(
                    blank=True, default="", max_length=160,
                    verbose_name="Organisme/employeur")),
                ("date_debut", models.DateField(
                    blank=True, null=True, verbose_name="Date de début")),
                ("date_fin", models.DateField(
                    blank=True, null=True, verbose_name="Date de fin")),
                ("description", models.CharField(
                    blank=True, default="", max_length=500,
                    verbose_name="Description")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_lignes_parcours",
                    to="authentication.company", verbose_name="Société")),
                ("employe", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="lignes_parcours",
                    to="rh.dossieremploye", verbose_name="Employé")),
                ("type", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="lignes",
                    to="rh.typeligneparcours", verbose_name="Type")),
            ],
            options={
                "verbose_name": "Ligne de parcours",
                "verbose_name_plural": "Lignes de parcours",
                "ordering": ["-date_debut", "-date_creation"],
            },
        ),
        migrations.AddIndex(
            model_name="ligneparcours",
            index=models.Index(
                fields=["company", "employe"],
                name="rh_ligne_parcours_emp_idx"),
        ),
    ]
