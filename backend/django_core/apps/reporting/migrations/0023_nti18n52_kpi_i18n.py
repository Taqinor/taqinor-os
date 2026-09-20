"""NTI18N52 — deux nouveaux membres du catalogue fermé ``KpiAlerte.Kpi``.

``couverture_i18n_pct`` (lit le dernier ``core.I18nCoverageSnapshot`` produit
par le job Beat hebdomadaire NTI18N39) et ``documents_non_fr_pct`` (non
évaluable aujourd'hui — aucune trace de la langue d'un PDF généré n'existe en
base ; voir ``apps/reporting/i18n_kpi.py``), tous deux calculés par
``apps.reporting.kpi_alertes`` via le sélecteur dédié
``apps.reporting.i18n_kpi`` (aucun import de modèle métier — ``reporting``
reste un satellite).

``AlterField`` sur ``choices`` UNIQUEMENT : ``documents_non_fr_pct`` fait 20
caractères, ``max_length`` reste 40. Même motif que les migrations 0012
(NTLOG51), 0013 (NTSCM46), 0018 (NTJUR48) et 0020 (NTCON34) : garder le modèle
et l'état de migration en phase (``makemigrations --check --dry-run`` en CI).
Aucune donnée touchée, entièrement revertable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0022_ntdata41_mode_detection'),
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
                    ('couverture_i18n_pct',
                     "i18n — couverture de l'interface (%)"),
                    ('documents_non_fr_pct',
                     'i18n — documents générés hors FR (%)'),
                ],
                default='', max_length=40),
        ),
    ]
