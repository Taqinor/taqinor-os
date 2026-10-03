"""AGR615 — type de relevé compteur « m³ » (index du compteur d'eau d'une
pompe solaire). AlterField de choix uniquement (max_length inchangé) :
additif et réversible, aucune donnée existante modifiée."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0064_solmvp14_detacher_apps_parquees'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relevecompteurequipement',
            name='type',
            field=models.CharField(
                choices=[('heures', 'Heures'), ('kwh', 'kWh'), ('m3', 'm³')],
                max_length=10),
        ),
    ]
