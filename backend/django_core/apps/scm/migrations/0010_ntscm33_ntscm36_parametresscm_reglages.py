# NTSCM33/NTSCM36 — enrichit ParametresSCM (migration additive, annoncée par
# la docstring de 0009_parametresscm.py) : horizon de prévision par défaut,
# niveaux de service par défaut par classe ABC, seuils d'alerte (écart délai
# fournisseur / score fournisseur / écart financier), rétention des
# prévisions. Tous les nouveaux champs portent un défaut IDENTIQUE aux
# constantes qu'ils remplacent (`services.SERVICE_LEVEL_PAR_CLASSE`,
# `selectors.SEUIL_ALERTE_ECART_CA_PCT`) : aucune régression de comportement
# pour une société qui n'a jamais rien configuré.
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scm', '0009_parametresscm'),
    ]

    operations = [
        migrations.AddField(
            model_name='parametresscm',
            name='horizon_prevision_mois_defaut',
            field=models.PositiveSmallIntegerField(
                default=3, verbose_name='Horizon de prévision par défaut (mois)'),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='service_level_defaut_a_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('95'), max_digits=5,
                verbose_name='Niveau de service par défaut — classe A (%)'),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='service_level_defaut_b_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('90'), max_digits=5,
                verbose_name='Niveau de service par défaut — classe B (%)'),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='service_level_defaut_c_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('85'), max_digits=5,
                verbose_name='Niveau de service par défaut — classe C (%)'),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='seuil_ecart_delai_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('20'), max_digits=5,
                verbose_name="Seuil d'alerte écart délai fournisseur (%)"),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='seuil_alerte_score_fournisseur_pts',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('15'), max_digits=5,
                verbose_name="Seuil d'alerte score fournisseur (points)"),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='seuil_alerte_ecart_financier_pct',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('15'), max_digits=5,
                verbose_name="Seuil d'alerte écart financier CA prévisionnel (%)"),
        ),
        migrations.AddField(
            model_name='parametresscm',
            name='retention_previsions_mois',
            field=models.PositiveSmallIntegerField(
                default=24, verbose_name='Rétention des prévisions (mois)'),
        ),
    ]
