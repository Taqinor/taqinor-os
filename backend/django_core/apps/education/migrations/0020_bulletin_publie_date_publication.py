# NTEDU33 — Portail parents : un bulletin n'est visible qu'après publication
# explicite (jamais le brouillon de l'enseignant).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0019_ligneecheance_transport_montant'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulletin',
            name='publie',
            field=models.BooleanField(default=False, verbose_name='Publié'),
        ),
        migrations.AddField(
            model_name='bulletin',
            name='date_publication',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Date de publication'),
        ),
    ]
