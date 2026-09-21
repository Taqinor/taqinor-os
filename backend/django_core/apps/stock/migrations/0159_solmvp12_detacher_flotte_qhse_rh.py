# SOLMVP12 (20/09/2026) — détache stock des modules flotte/qhse/rh (parqués).
#
# RemoveField destructif-revertable : seules les COLONNES DE LIEN partent,
# aucune table supprimée, aucune ligne django_migrations touchée. Les 4 FK
# gardé→parqué inventoriées le 20/09 pour stock :
#   * StockVehicule.actif_flotte    -> 'flotte.ActifFlotte' (van sales, NTDST14
#     — fonctionnalité retirée avec le lien, cf. models_van_sales.py) ;
#   * PlanChargement.vehicule       -> 'flotte.Vehicule' (optionnel, NTWMS26) ;
#   * BlocageQualite.non_conformite -> 'qhse.NonConformite' (optionnel, NTWMS31) ;
#   * BudgetDepartement.departement -> 'rh.Departement' (NTP2P4 — l'enveloppe
#     budgétaire devient unique par société + période au lieu de par
#     département).
#
# Les contraintes/index qui référençaient ces deux dernières colonnes doivent
# partir avec elles (une UniqueConstraint/Index ne peut pas survivre à la
# colonne qu'elle indexe) : StockVehicule perd sa contrainte unique
# (société, véhicule, produit) et son index (plus de distinction par
# véhicule) ; BudgetDepartement perd son index départemental et voit sa
# contrainte unique RÉTRÉCIE à (société, périodicité, année, mois) — UNE
# seule enveloppe par société et par période, recréée par AddConstraint sous
# le MÊME nom pour ne rien casser côté code applicatif.
#
# Retour d'un module parqué (recette « coquille de migrations », voir
# docs/parked-modules.md) : restaurer son dossier + `migrate <app> <n-1>` sur
# CETTE migration réapplique l'état d'AVANT (Django recrée la colonne) —
# aucune donnée de lien n'est perdue au niveau SQL tant que ce revert n'a pas
# eu lieu ; les valeurs existantes de ces colonnes sont perdues par ce
# RemoveField lui-même (comportement standard d'un RemoveField), noté au
# DONE LOG.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0158_ntp2p35_purge_brouillon_jours'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='stockvehicule',
            options={
                'ordering': ['produit_id'],
                'verbose_name': 'Stock embarqué véhicule',
                'verbose_name_plural': 'Stocks embarqués véhicule',
            },
        ),
        migrations.RemoveConstraint(
            model_name='budgetdepartement',
            name='uniq_budget_dep_periode',
        ),
        migrations.RemoveConstraint(
            model_name='stockvehicule',
            name='stock_stockvehicule_co_actif_produit_uniq',
        ),
        migrations.RemoveIndex(
            model_name='budgetdepartement',
            name='idx_budgdep_co_dept',
        ),
        migrations.RemoveIndex(
            model_name='stockvehicule',
            name='idx_stockveh_co_actif',
        ),
        migrations.RemoveField(
            model_name='stockvehicule',
            name='actif_flotte',
        ),
        migrations.RemoveField(
            model_name='planchargement',
            name='vehicule',
        ),
        migrations.RemoveField(
            model_name='blocagequalite',
            name='non_conformite',
        ),
        migrations.RemoveField(
            model_name='budgetdepartement',
            name='departement',
        ),
        migrations.AddConstraint(
            model_name='budgetdepartement',
            constraint=models.UniqueConstraint(
                fields=('company', 'periodicite', 'annee', 'mois'),
                name='uniq_budget_dep_periode'),
        ),
    ]
