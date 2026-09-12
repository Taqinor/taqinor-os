"""NTJUR48 — quatre nouveaux membres du catalogue fermé ``KpiAlerte.Kpi``.

``juridique_dossiers_ouverts``, ``juridique_montant_en_jeu_total``,
``juridique_taux_gain`` et ``juridique_delai_moyen_resolution``, calculés par
``apps.reporting.kpi_alertes`` via ``apps.juridique.selectors.kpis_juridiques``
(aucun import de modèle croisé — ``reporting`` reste un satellite).

``AlterField`` sur ``choices`` ET sur ``max_length`` (30 → 40) :
``juridique_delai_moyen_resolution`` fait 32 caractères. C'est un
ÉLARGISSEMENT pur — aucune valeur existante ne dépasse 30, donc aucune
troncature possible ; en PostgreSQL l'élargissement d'un ``varchar`` est une
opération de MÉTADONNÉES (pas de réécriture de table). Même motif que les
migrations 0012 (NTLOG51) et 0013 (NTSCM46) pour la partie ``choices`` :
garder le modèle et l'état de migration en phase
(``makemigrations --check --dry-run`` en CI).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0017_aud803_revocation_partage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kpialerte',
            name='kpi',
            field=models.CharField(
                choices=[
                    ('dso', 'DSO (délai moyen de recouvrement, jours)'),
                    ('encours_echu_total', 'Encours client échu total (MAD)'),
                    ('valeur_stock_totale', 'Valeur de stock totale (MAD)'),
                    ('delai_moyen_dedouanement',
                     'Délai moyen de dédouanement (jours)'),
                    ('taux_service_scm', 'Supply chain — taux de service (%)'),
                    ('juridique_dossiers_ouverts',
                     'Juridique — dossiers ouverts'),
                    ('juridique_montant_en_jeu_total',
                     'Juridique — montant total en jeu (MAD)'),
                    ('juridique_taux_gain', 'Juridique — taux de gain (%)'),
                    ('juridique_delai_moyen_resolution',
                     'Juridique — délai moyen de résolution (jours)'),
                ],
                max_length=40),
        ),
    ]
