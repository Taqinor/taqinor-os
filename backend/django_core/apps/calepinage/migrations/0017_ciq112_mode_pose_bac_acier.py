# CIQ112 (Groupe CIQ) — choix « bac acier » ajouté à
# ``SystemeFixation.ModePose``. Ajout de CHOIX seulement (aucune colonne,
# aucune donnée réécrite) : réversible par l'AlterField inverse.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0016_calx406_responsable'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemefixation',
            name='mode_pose',
            field=models.CharField(
                choices=[('toiture_inclinee', 'Toiture inclinée'),
                         ('bac_acier', 'Bac acier'),
                         ('toit_plat_leste', 'Toit plat — lesté'),
                         ('toit_plat_fixe', 'Toit plat — fixé'),
                         ('sol', 'Au sol'),
                         ('ombriere', 'Ombrière'),
                         ('autre', 'Autre')],
                default='toiture_inclinee', max_length=20,
                verbose_name='Mode de pose'),
        ),
    ]
