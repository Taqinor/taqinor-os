# NTEDU19 — Paramètres école (singleton par société).

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0008_certificatscolarite'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresEducation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_echeances_defaut', models.PositiveIntegerField(default=10, verbose_name="Nombre d'échéances par défaut")),
                ('taux_remise_fratrie_defaut', models.DecimalField(decimal_places=2, default=Decimal('10'), max_digits=5, verbose_name='Taux de remise fratrie par défaut (%)')),
                ('grille_mentions', models.JSONField(blank=True, default=dict, verbose_name='Grille des mentions')),
                ('delai_relance_impaye_jours', models.PositiveIntegerField(default=15, verbose_name="Délai de relance impayé (jours)")),
                ('devise', models.CharField(default='MAD', max_length=3, verbose_name='Devise')),
                ('notifier_incidents_mineurs', models.BooleanField(default=False, verbose_name='Notifier les incidents mineurs')),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='education_parametres', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Paramètres éducation',
                'verbose_name_plural': 'Paramètres éducation',
            },
        ),
    ]
