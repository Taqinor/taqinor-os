"""HOLIDAY-PAYS (complément NTI18N13) — ``Holiday.pays`` (ISO 3166-1
alpha-2, défaut 'MA'). Additif : toutes les lignes existantes (calendrier
marocain) reçoivent 'MA', zéro régression pour les sociétés MA en place."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0062_eventtype_notifications_portail'),
    ]

    operations = [
        migrations.AddField(
            model_name='holiday',
            name='pays',
            field=models.CharField(
                default='MA', help_text='Code pays ISO du jour férié (MA = Maroc).',
                max_length=2, verbose_name='Pays (ISO 3166-1 alpha-2)'),
        ),
    ]
