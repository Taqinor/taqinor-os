"""PV54 — ``ZoneAO`` : le contour NOMMÉ d'une toiture.

Purement ADDITIVE : une seule table neuve, aucune colonne touchée sur une table
existante, aucune donnée déplacée. Réversible sans perte (``migrate ao 0021``
supprime une table qui n'existait pas avant).
"""
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0021_uniques_ydata'),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZoneAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('repere', models.CharField(blank=True, default='', max_length=16, verbose_name='Repère (Z1, Z2…)')),
                ('nature', models.CharField(choices=[('ENVELOPPE', 'Enveloppe posable'), ('INTERDITE', 'Zone interdite'), ('RESERVEE', 'Zone réservée (technique, circulation)'), ('PREFEREE', 'Zone préférée')], default='INTERDITE', max_length=12, verbose_name='Nature')),
                ('sommets', models.JSONField(blank=True, default=list, verbose_name='Sommets [x, y] en mètres (repère local)')),
                ('hauteur_m', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Hauteur (m)')),
                ('retrait_m', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Retrait (m)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zones_ao', to='authentication.company', verbose_name='Société')),
                ('toiture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zones', to='ao.toitureao', verbose_name='Toiture')),
            ],
            options={
                'verbose_name': 'Zone de toiture (AO)',
                'verbose_name_plural': 'Zones de toiture (AO)',
                'db_table': 'ao_zone',
                'ordering': ['toiture', 'repere', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='zoneao',
            index=models.Index(fields=['company', 'toiture'], name='ao_zone_company_toiture_idx'),
        ),
        migrations.AddConstraint(
            model_name='zoneao',
            constraint=models.UniqueConstraint(
                condition=models.Q(('repere', ''), _negated=True),
                fields=('company', 'toiture', 'repere'),
                name='uniq_zone_repere_par_toiture'),
        ),
    ]
