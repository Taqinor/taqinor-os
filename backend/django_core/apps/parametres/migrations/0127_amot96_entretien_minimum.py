"""AMOT96 (D-ACI-14=a) — réglage société ``entretien_minimum_mad_kwc_an``.

ADDITIF : une colonne décimale NULL (NULL = entretien non chiffré : le flux
C&I reste celui d'hier). Réversible : ``python manage.py migrate parametres
0126``.
"""
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
                blank=True, decimal_places=2, max_digits=10, null=True,
                help_text='Déduit des économies C&I quand aucune O&M n’est '
                          'souscrite ; vide = entretien non chiffré.',
                verbose_name='Entretien minimum à la charge du client '
                             '(MAD HT/kWc/an)'),
        ),
    ]
