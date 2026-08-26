"""AUTO-PIPELINE — reglage de societe « devis automatique depuis le tunnel ».

Additive et reversible : un simple booleen, actif par defaut (c'est le flux
demande par le fondateur le 26/08/2026). Aucune donnee existante n'est touchee.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0078_cadencerelanceetape'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='devis_auto_depuis_tunnel',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Crée automatiquement un devis BROUILLON (à vérifier) dès '
                    "qu'un lead du site web arrive avec assez de données "
                    'réelles pour être dimensionné. Décochez pour revenir à la '
                    'création manuelle.'),
                verbose_name='Devis automatique depuis le tunnel'),
        ),
    ]
