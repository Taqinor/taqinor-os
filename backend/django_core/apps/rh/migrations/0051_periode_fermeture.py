# XRH14 — Fermetures collectives / congés imposés.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0050_employe_device_map"),
    ]

    operations = [
        migrations.CreateModel(
            name="PeriodeFermeture",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("libelle", models.CharField(max_length=200)),
                ("date_debut", models.DateField()),
                ("date_fin", models.DateField()),
                ("appliquee", models.BooleanField(default=False)),
                ("appliquee_le", models.DateTimeField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rh_periodes_fermeture",
                    to="authentication.company")),
                ("type_absence", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="periodes_fermeture", to="rh.typeabsence")),
                ("departements", models.ManyToManyField(
                    blank=True, related_name="periodes_fermeture",
                    to="rh.departement")),
            ],
            options={
                "verbose_name": "Fermeture collective",
                "verbose_name_plural": "Fermetures collectives",
                "ordering": ["-date_debut"],
            },
        ),
        migrations.AddIndex(
            model_name="periodefermeture",
            index=models.Index(
                fields=["company", "date_debut", "date_fin"],
                name="rh_fermeture_comp_dates_idx"),
        ),
    ]
