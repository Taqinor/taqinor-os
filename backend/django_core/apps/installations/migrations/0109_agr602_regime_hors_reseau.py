"""AGR602 — régime « déclaration hors réseau » (loi 82-21, art. 3).

ADDITIF et réversible : nouveau choix ``declaration_hors_reseau`` sur
``Installation.regime_8221`` (AlterField de choix, max_length inchangé) et
champ ``raccordement_reseau`` (hors_reseau | raccorde, nullable). Aucun
chantier existant n'est touché (valeur nulle par défaut).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0108_cal210_reservation_origine_calepinage'),
    ]

    operations = [
        migrations.AddField(
            model_name='installation',
            name='raccordement_reseau',
            field=models.CharField(
                blank=True,
                choices=[('hors_reseau', 'Hors réseau'),
                         ('raccorde', 'Raccordé au réseau')],
                max_length=12, null=True),
        ),
        migrations.AlterField(
            model_name='installation',
            name='regime_8221',
            field=models.CharField(
                choices=[
                    ('non_concerne', 'Non concerné'),
                    ('declaration_bt', 'Déclaration (< 11 kW, BT)'),
                    ('accord_raccordement', 'Accord de raccordement'),
                    ('autorisation_anre', 'Autorisation ANRE (> 1 MW)'),
                    ('declaration_hors_reseau',
                     'Déclaration hors réseau (loi 82-21, art. 3)'),
                ],
                default='non_concerne', max_length=24),
        ),
    ]
