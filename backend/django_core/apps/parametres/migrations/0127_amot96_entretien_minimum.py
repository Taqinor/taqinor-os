"""AMOT96 (D-ACI-14=a) — réglage société ``entretien_minimum_mad_kwc_an``.

ADDITIF : une colonne décimale NULL, sans défaut (vide = entretien non
chiffré, flux C&I inchangé). Réversible : ``python manage.py migrate
parametres 0126``.
"""
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0126_acrm66_apporteurs_actif'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='entretien_minimum_mad_kwc_an',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                validators=[django.core.validators.MinValueValidator(
                    Decimal('0'))],
                verbose_name='Entretien minimum à la charge du client '
                             '(MAD HT/kWc/an)'),
        ),
    ]
