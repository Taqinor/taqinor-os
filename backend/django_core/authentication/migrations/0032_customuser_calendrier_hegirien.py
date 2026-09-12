"""NTI18N12 — préférence d'affichage « calendrier hégirien » (jamais stocké
en tant que date, affichage seul).

Additive : défaut False, tout compte existant est inchangé.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0031_customuser_langue_interface'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='calendrier_hegirien',
            field=models.BooleanField(
                default=False,
                help_text='Montre la date hégirienne à côté de la date '
                          'grégorienne (affichage seul, jamais stocké) quand '
                          "la langue d'interface est l'arabe.",
                verbose_name='Afficher le calendrier hégirien'),
        ),
    ]
