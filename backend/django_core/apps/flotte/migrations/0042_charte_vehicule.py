# Generated for XFLT17 — Charte véhicule + signatures sur l'état des lieux.
# Ajoute des champs additifs sur ``EtatDesLieux`` (signatures + accessoires)
# et crée ``CharteVehicule`` / ``AccuseCharte``. Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0041_vehicule_cession"),
    ]

    operations = [
        migrations.AddField(
            model_name="etatdeslieux",
            name="signature_conducteur",
            field=models.CharField(
                blank=True, max_length=150,
                verbose_name="Signature conducteur (nom saisi)"),
        ),
        migrations.AddField(
            model_name="etatdeslieux",
            name="signature_conducteur_horodatage",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Horodatage signature conducteur"),
        ),
        migrations.AddField(
            model_name="etatdeslieux",
            name="signature_responsable",
            field=models.CharField(
                blank=True, max_length=150,
                verbose_name="Signature responsable (nom saisi)"),
        ),
        migrations.AddField(
            model_name="etatdeslieux",
            name="signature_responsable_horodatage",
            field=models.DateTimeField(
                blank=True, null=True,
                verbose_name="Horodatage signature responsable"),
        ),
        migrations.AddField(
            model_name="etatdeslieux",
            name="accessoires",
            field=models.JSONField(
                blank=True, default=list,
                help_text='[{"nom": "Gilet", "present": true}, …]',
                verbose_name="Accessoires"),
        ),
        migrations.CreateModel(
            name="CharteVehicule",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("version", models.PositiveIntegerField(verbose_name="Version")),
                ("document", models.FileField(
                    upload_to="flotte/chartes_vehicule/%Y/%m/",
                    verbose_name="Document (charte véhicule)")),
                ("date_publication", models.DateTimeField(
                    auto_now_add=True, verbose_name="Date de publication")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_chartes_vehicule",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Charte véhicule",
                "verbose_name_plural": "Chartes véhicule",
                "ordering": ["-version"],
            },
        ),
        migrations.AddConstraint(
            model_name="chartevehicule",
            constraint=models.UniqueConstraint(
                fields=("company", "version"),
                name="flotte_chartevehicule_company_version_uniq"),
        ),
        migrations.CreateModel(
            name="AccuseCharte",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("version", models.PositiveIntegerField(
                    verbose_name="Version de la charte accusée")),
                ("date_accuse", models.DateTimeField(
                    auto_now_add=True, verbose_name="Date de l'accusé")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_accuses_charte",
                    to="authentication.company", verbose_name="Société")),
                ("conducteur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_accuses_charte",
                    to="flotte.conducteur", verbose_name="Conducteur")),
            ],
            options={
                "verbose_name": "Accusé de charte véhicule",
                "verbose_name_plural": "Accusés de charte véhicule",
                "ordering": ["-date_accuse"],
            },
        ),
        migrations.AddConstraint(
            model_name="accusecharte",
            constraint=models.UniqueConstraint(
                fields=("company", "conducteur", "version"),
                name="flotte_accusecharte_co_cond_ver_uniq"),
        ),
    ]
