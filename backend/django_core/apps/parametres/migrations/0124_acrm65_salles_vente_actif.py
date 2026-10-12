"""ACRM65 — réglage société ``salles_vente_actif`` (salles de vente parquées).

ADDITIF : une colonne booléenne, défaut False (salles parquées ; aucune donnée
supprimée). Réversible : ``python manage.py migrate parametres 0123``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0123_apdf21_identite_legale'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='salles_vente_actif',
            field=models.BooleanField(
                default=False,
                help_text='OFF = salles de vente parquées (rien servi, rien '
                          'supprimé). ON = salles de vente servies comme avant.',
                verbose_name='Salles de vente digitales actives'),
        ),
    ]
