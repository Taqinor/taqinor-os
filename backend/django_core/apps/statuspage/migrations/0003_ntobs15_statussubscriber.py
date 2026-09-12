# NTOBS15 — abonnement aux notifications d'incidents (page de statut
# publique). Migration ecrite a la main (INTERDIT manage.py sur cette
# lane) ; state Django equivalent a ce que `makemigrations` produirait pour
# `apps.statuspage.models.StatusSubscriber`.
from django.db import migrations, models

import apps.statuspage.models


class Migration(migrations.Migration):

    dependencies = [
        ('statuspage', '0002_ntobs14_uptimedaybucket'),
    ]

    operations = [
        migrations.CreateModel(
            name='StatusSubscriber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='E-mail')),
                ('region_filtre', models.CharField(blank=True, default='', help_text='Vide = toutes régions.', max_length=60, verbose_name='Région (filtre)')),
                ('token_desabonnement', models.CharField(default=apps.statuspage.models._default_subscriber_token, max_length=64, unique=True)),
                ('confirme', models.BooleanField(default=False, verbose_name='Confirmé (double opt-in)')),
            ],
            options={
                'verbose_name': 'Abonné (statut public)',
                'verbose_name_plural': 'Abonnés (statut public)',
                'ordering': ['email'],
            },
        ),
    ]
