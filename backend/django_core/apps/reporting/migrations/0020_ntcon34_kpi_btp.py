"""NTCON34 — quatre nouveaux membres du catalogue fermé ``KpiAlerte.Kpi``.

``btp_reserves_ouvertes``, ``btp_rfi_en_retard``, ``btp_visas_en_attente`` et
``btp_penalites_cumulees_periode``, calculés par ``apps.reporting.kpi_alertes``
via ``apps.btp_chantier.selectors.kpis_btp`` (aucun import de modèle croisé —
``reporting`` reste un satellite).

``AlterField`` sur ``choices`` UNIQUEMENT : ``btp_penalites_cumulees_periode``
fait 30 caractères, ``max_length`` reste 40. Même motif que les migrations
0012 (NTLOG51), 0013 (NTSCM46) et 0018 (NTJUR48) : garder le modèle et l'état
de migration en phase (``makemigrations --check --dry-run`` en CI). Aucune
donnée touchée, entièrement revertable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0019_ntdata13_alerte_sur_metrique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kpialerte',
            name='kpi',
            field=models.CharField(
                blank=True,
                choices=[
                    ('dso', 'DSO (délai moyen de recouvrement, jours)'),
                    ('encours_echu_total',
                     'Encours client échu total (MAD)'),
                    ('valeur_stock_totale',
                     'Valeur de stock totale (MAD)'),
                    ('delai_moyen_dedouanement',
                     'Délai moyen de dédouanement (jours)'),
                    ('taux_service_scm',
                     'Supply chain — taux de service (%)'),
                    ('juridique_dossiers_ouverts',
                     'Juridique — dossiers ouverts'),
                    ('juridique_montant_en_jeu_total',
                     'Juridique — montant total en jeu (MAD)'),
                    ('juridique_taux_gain', 'Juridique — taux de gain (%)'),
                    ('juridique_delai_moyen_resolution',
                     'Juridique — délai moyen de résolution (jours)'),
                    ('btp_reserves_ouvertes', 'BTP — réserves ouvertes'),
                    ('btp_rfi_en_retard',
                     'BTP — RFI en retard de réponse'),
                    ('btp_visas_en_attente',
                     'BTP — visas en attente de revue'),
                    ('btp_penalites_cumulees_periode',
                     'BTP — exposition cumulée aux pénalités de retard (MAD)'),
                ],
                default='', max_length=40),
        ),
    ]
