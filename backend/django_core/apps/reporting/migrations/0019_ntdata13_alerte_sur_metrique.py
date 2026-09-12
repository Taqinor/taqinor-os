"""NTDATA13 — `KpiAlerte` peut cibler une métrique nommée (couche sémantique).

Additive et revertable : `source` par défaut `catalogue` = comportement
historique EXACT, `metric_definition` nullable, et `kpi` devient seulement
FACULTATIF (aucune valeur existante n'est touchée).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0018_ntjur48_kpi_juridiques'),
        ('semantic', '0002_ntdata11_filtres'),
    ]

    operations = [
        migrations.AddField(
            model_name='kpialerte',
            name='source',
            field=models.CharField(
                choices=[
                    ('catalogue', 'KPI du catalogue'),
                    ('metrique', 'Métrique nommée (couche sémantique)'),
                ],
                default='catalogue', max_length=12,
                verbose_name='Source du chiffre'),
        ),
        migrations.AddField(
            model_name='kpialerte',
            name='metric_definition',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='alertes_kpi', to='semantic.metricdefinition',
                verbose_name='Métrique nommée'),
        ),
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
                ],
                default='', max_length=40),
        ),
    ]
