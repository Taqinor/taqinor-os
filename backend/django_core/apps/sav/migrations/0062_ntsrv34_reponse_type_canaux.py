"""NTSRV34 - Modeles de reponse par canal (extension XSAV23), purement additif.

``ReponseType.canaux_autorises`` : liste JSON nullable de canaux
('email', 'whatsapp', 'portail', 'interne'). NULL sur toutes les macros
existantes = AUCUNE restriction, donc le selecteur de macros reste
strictement celui d'aujourd'hui tant qu'une societe ne restreint rien.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0061_ntsrv23_csat_detaille'),
    ]

    operations = [
        migrations.AddField(
            model_name='reponsetype',
            name='canaux_autorises',
            field=models.JSONField(
                blank=True, null=True,
                help_text="Liste de canaux ('email', 'whatsapp', 'portail', "
                          "'interne'). Vide = macro proposée sur TOUS les "
                          'canaux.',
                verbose_name='Canaux autorisés'),
        ),
    ]
