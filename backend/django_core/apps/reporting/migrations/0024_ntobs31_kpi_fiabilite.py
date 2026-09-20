"""NTOBS31 — trois nouveaux membres du catalogue fermé ``KpiAlerte.Kpi``.

``uptime_moyen_12_mois`` (moyenne des ``core.sla.SlaSnapshot.uptime_pct`` de
la société sur 12 mois), ``jours_depuis_dernier_drill_reussi`` (depuis le
dernier ``core.models.BackupRun`` de type ``restore_drill`` TERMINÉ) et
``quota_le_plus_charge_pct`` (max des ratios de ``core.usage_limits.
usage_summary``, NTOBS8) — tous calculés par ``apps.reporting.kpi_alertes``
via des sources DÉJÀ BÂTIES par le groupe NTOBS, aucun nouveau moteur de KPI.

``AlterField`` sur ``choices`` UNIQUEMENT : le plus long des trois
(``jours_depuis_dernier_drill_reussi``, 33 caractères) reste sous
``max_length`` (40). Même motif que les migrations 0012/0013/0018/0020/0023 :
garder le modèle et l'état de migration en phase
(``makemigrations --check --dry-run`` en CI). Aucune donnée touchée,
entièrement revertable.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0023_nti18n52_kpi_i18n'),
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
                    ('uptime_moyen_12_mois',
                     'Fiabilité — disponibilité moyenne 12 mois (%)'),
                    ('jours_depuis_dernier_drill_reussi',
                     'Fiabilité — jours depuis le dernier drill de '
                     'restauration réussi'),
                    ('quota_le_plus_charge_pct',
                     'Fiabilité — quota le plus chargé (%)'),
                ],
                default='', max_length=40),
        ),
    ]
