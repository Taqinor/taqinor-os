from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('gestion_projet', '0035_xprj27_projet_marche_public'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReglageTemps',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('arrondi_minutes', models.PositiveSmallIntegerField(
                    default=15, verbose_name="Pas d'arrondi (minutes)")),
                ('mode_arrondi', models.CharField(
                    choices=[
                        ('inferieur', 'Arrondi au pas inférieur'),
                        ('superieur', 'Arrondi au pas supérieur'),
                        ('proche', 'Arrondi au pas le plus proche'),
                    ],
                    default='superieur', max_length=10,
                    verbose_name="Mode d'arrondi")),
                ('unite_saisie', models.CharField(
                    choices=[('heures', 'Heures'), ('jours', 'Jours')],
                    default='heures', max_length=10,
                    verbose_name='Unité de saisie')),
                ('heures_par_jour', models.DecimalField(
                    decimal_places=2, default=Decimal('8'), max_digits=4,
                    verbose_name='Heures par jour')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gp_reglage_temps',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Réglage temps',
                'verbose_name_plural': 'Réglages temps',
                'ordering': ['id'],
            },
        ),
    ]
