# VTA10 — le module « Visites terrain » rejoint le vocabulaire de la file
# hors-ligne.
#
# Purement ADDITIVE et réversible : un choix de plus sur ``module``. Aucune
# donnée existante n'est touchée (la colonne est un CharField, la liste de
# choix ne sert qu'à la validation et à l'admin).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offlinesync', '0002_ntmob2_conflit_resolution'),
    ]

    operations = [
        migrations.AlterField(
            model_name='offlineoperation',
            name='module',
            field=models.CharField(
                choices=[('crm', 'CRM'), ('ventes', 'Ventes'),
                         ('stock', 'Stock'), ('installations', 'Chantiers'),
                         ('sav', 'SAV'), ('visites', 'Visites terrain')],
                db_index=True, max_length=20, verbose_name='Module cible'),
        ),
    ]
