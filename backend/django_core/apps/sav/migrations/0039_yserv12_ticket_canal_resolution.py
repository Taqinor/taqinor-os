# YSERV12 — Canal de résolution du ticket (à distance / sur site).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0038_yserv5_generation_auto_visites'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='canal_resolution',
            field=models.CharField(
                blank=True, null=True,
                choices=[
                    ('a_distance', 'À distance'),
                    ('sur_site', 'Sur site'),
                ],
                max_length=12,
                help_text='Résolu à distance (téléphone/redémarrage) ou sur '
                          'site (déplacement). Vide = non renseigné '
                          '(tickets anciens).',
                verbose_name='Canal de résolution'),
        ),
    ]
