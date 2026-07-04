# Generated for XRH33 — publication publique des offres d'emploi (careers,
# flag-gated OFF par défaut). Additif : les ouvertures existantes restent
# non publiées (publiee=False).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0065_pulse_enps'),
    ]

    operations = [
        migrations.AddField(
            model_name='ouvertureposte',
            name='ville',
            field=models.CharField(
                blank=True, default='', max_length=120,
                verbose_name='Ville'),
        ),
        migrations.AddField(
            model_name='ouvertureposte',
            name='publiee',
            field=models.BooleanField(
                default=False, verbose_name='Publiée (carrières)'),
        ),
    ]
