"""NTLOG51 (volet douane) — nouveau membre du catalogue fermé
``KpiAlerte.Kpi`` : ``delai_moyen_dedouanement`` (« Délai moyen de
dédouanement (jours) »), calculé par ``apps.reporting.kpi_alertes.
_compute_delai_moyen_dedouanement`` via ``apps.douane.selectors.
delai_moyen_dedouanement`` (aucune nouvelle table : lit la trace d'audit
générique déjà posée par ``apps.douane.services.
tracer_transition_statut_dossier_export``).

``AlterField`` pur sur ``choices`` — CharField, donc AUCUN effet de schéma
base de données ; garde uniquement le modèle et l'état de migration en phase
(``scripts/preflight.ps1`` / CI ``makemigrations --check --dry-run``).

Volet apps/transport (« Coût transport / kg », « Taux de litiges transport »)
HORS PÉRIMÈTRE de cette migration — lane concurrente sur ce même fichier
``apps/reporting/models.py`` (voir docs/plans/PLAN_SUPPLY.md NTLOG51)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0011_ntext12_rapportabonnement'),
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
                ],
                max_length=30),
        ),
    ]
