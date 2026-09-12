# NTHCM21 — titre (habilitation/certification) délivré par un parcours.
#
# ADDITIF et SÛR : trois AddField à défaut vide/NULL sur une table neuve
# (NTHCM17) — aucun AddField(unique), aucun NOT NULL sans défaut (YDATA20).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0098_nthcm19_rappel_parcours'),
    ]

    operations = [
        migrations.AddField(
            model_name='parcoursformation',
            name='habilitation_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('b0', "B0 — Non-électricien (travaux d'ordre non "
                           'électrique BT)'),
                    ('h0', 'H0 — Non-électricien (zone HT)'),
                    ('h0v', 'H0V — Non-électricien (voisinage HT)'),
                    ('b1', 'B1 — Exécutant électricien BT'),
                    ('b1v', 'B1V — Exécutant électricien BT (voisinage)'),
                    ('b2', 'B2 — Chargé de travaux BT'),
                    ('b2v', 'B2V — Chargé de travaux BT (voisinage)'),
                    ('br', "BR — Chargé d'intervention générale BT"),
                    ('bc', 'BC — Chargé de consignation BT'),
                    ('be', "BE — Chargé d'opérations spécifiques BT"),
                    ('h1', 'H1 — Exécutant électricien HT'),
                    ('h1v', 'H1V — Exécutant électricien HT (voisinage)'),
                    ('h2', 'H2 — Chargé de travaux HT'),
                    ('h2v', 'H2V — Chargé de travaux HT (voisinage)'),
                    ('hc', 'HC — Chargé de consignation HT'),
                    ('bp', 'BP — Photovoltaïque (opérations sur installation '
                           'PV)'),
                    ('autre', 'Autre'),
                ],
                default='', max_length=10,
                verbose_name='Habilitation délivrée'),
        ),
        migrations.AddField(
            model_name='parcoursformation',
            name='certification_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('travail_hauteur', 'Travail en hauteur'),
                    ('harnais', 'Port du harnais / EPI antichute'),
                    ('caces_nacelle', 'CACES / nacelle (PEMP)'),
                    ('secourisme_sst', 'Secourisme du travail (SST)'),
                    ('conduite', 'Conduite (permis / engins)'),
                    ('autre', 'Autre'),
                ],
                default='', max_length=20,
                verbose_name='Certification délivrée'),
        ),
        migrations.AddField(
            model_name='parcoursformation',
            name='validite_mois',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Validité du titre délivré (mois)'),
        ),
    ]
