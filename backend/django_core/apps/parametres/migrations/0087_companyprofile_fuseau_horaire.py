"""NTI18N10 — fuseau horaire d'AFFICHAGE de la société.

Additive : défaut 'Africa/Casablanca' = comportement historique inchangé
pour toute société existante. Ne change RIEN au stockage (toujours UTC).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0086_realisation'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='fuseau_horaire',
            field=models.CharField(
                default='Africa/Casablanca', max_length=64,
                help_text='Fuseau IANA (ex. Africa/Casablanca, Africa/Dakar) '
                          "utilisé pour AFFICHER les dates/heures côté "
                          'frontend — le stockage reste UTC, sans changement.',
                verbose_name='Fuseau horaire'),
        ),
    ]
