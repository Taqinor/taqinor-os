# XPLT14 — custom_data sur DossierEmploye (couverture module 'employe').

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0044_horaire_travail"),
    ]

    operations = [
        migrations.AddField(
            model_name="dossieremploye",
            name="custom_data",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
