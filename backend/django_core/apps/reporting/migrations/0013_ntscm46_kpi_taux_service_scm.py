"""NTSCM46 — nouveau membre du catalogue fermé ``KpiAlerte.Kpi`` :
``taux_service_scm`` (« Supply chain — taux de service (%) »), calculé par
``apps.reporting.kpi_alertes._compute_taux_service_scm`` via
``apps.scm.selectors.tableau_bord_executif`` (NTSCM28, réutilisé tel quel —
aucun système de KPI parallèle).

``AlterField`` pur sur ``choices`` — CharField, donc AUCUN effet de schéma
base de données ; garde uniquement le modèle et l'état de migration en phase
(``scripts/preflight.ps1`` / CI ``makemigrations --check --dry-run``), même
motif que la migration 0012 (NTLOG51)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0012_ntlog51_kpi_delai_dedouanement'),
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
                ],
                max_length=30),
        ),
    ]
