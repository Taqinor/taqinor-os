"""XACC32 — Prorata temporis sur la 1re annuité d'amortissement linéaire.

Additif : ``Immobilisation.date_mise_en_service`` (nullable, défaut effectif
= date_acquisition côté modèle) pour calculer, en linéaire, la 1re dotation
au prorata des mois restants (CGI marocain).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0063_notefrais_refacturation'),
    ]

    operations = [
        migrations.AddField(
            model_name='immobilisation',
            name='date_mise_en_service',
            field=models.DateField(blank=True, null=True, verbose_name='Date de mise en service'),
        ),
    ]
