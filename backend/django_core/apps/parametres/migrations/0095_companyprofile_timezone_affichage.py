"""NTOBS23 — fuseau horaire d'affichage par tenant (horodatages du groupe
Fiabilité — NTOBS1/3/9), stockés en UTC mais affichés bruts aujourd'hui.

Additif : défaut 'Africa/Casablanca' = comportement historique inchangé pour
toute société existante.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0094_companyprofile_langue_interface_verrouillee'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='timezone_affichage',
            field=models.CharField(
                default='Africa/Casablanca',
                help_text='Nom de fuseau IANA (ex. Africa/Casablanca, '
                          'Europe/Paris) utilisé pour afficher les '
                          'horodatages générés côté serveur. Défaut '
                          'Africa/Casablanca (comportement historique '
                          'inchangé).',
                max_length=50,
                verbose_name="Fuseau horaire d'affichage"),
        ),
    ]
