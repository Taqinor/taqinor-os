"""ODX15 — sortie state-only des notes de frais vers ``apps.frais``.

``SeparateDatabaseAndState`` avec ``database_operations=[]`` : les 5
modèles (NoteFrais, RapportNoteFrais, PlafondNoteFrais, BaremeIndemnite,
IndemniteChantier) quittent l'ÉTAT de compta sans qu'aucune table ne soit
touchée. ``apps/frais/migrations/0001_odx15_frais_split.py`` les recrée
dans l'état sur les MÊMES tables (``db_table='compta_*'``) et dépend de
cette migration : aucun instant n'a deux modèles pour une même table.

ADDITIF ET RÉVERSIBLE : l'inverse est lui aussi state-only (aucun DROP,
aucune donnée perdue) — un ``git revert`` suffit.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0121_retenuesource_convention_appliquee_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='bareme',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='compte_charge',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='compte_tresorerie',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='created_by',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='ecriture_charge',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='ecriture_remboursement',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='employe',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='rembourse_par',
                ),
                migrations.RemoveField(
                    model_name='indemnitechantier',
                    name='valide_par',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='compte_charge',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='compte_tresorerie',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='created_by',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='ecriture_charge',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='ecriture_remboursement',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='employe',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='rapport',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='rembourse_par',
                ),
                migrations.RemoveField(
                    model_name='notefrais',
                    name='valide_par',
                ),
                migrations.RemoveField(
                    model_name='plafondnotefrais',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='company',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='compte_tresorerie',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='created_by',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='ecriture_charge',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='ecriture_remboursement',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='employe',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='rembourse_par',
                ),
                migrations.RemoveField(
                    model_name='rapportnotefrais',
                    name='valide_par',
                ),
                migrations.DeleteModel(
                    name='BaremeIndemnite',
                ),
                migrations.DeleteModel(
                    name='IndemniteChantier',
                ),
                migrations.DeleteModel(
                    name='NoteFrais',
                ),
                migrations.DeleteModel(
                    name='PlafondNoteFrais',
                ),
                migrations.DeleteModel(
                    name='RapportNoteFrais',
                ),
            ],
            # ODX15 — ZÉRO SQL : les tables restent celles de compta
            # (db_table 'compta_*' figé sur chaque modèle).
            database_operations=[],
        ),
    ]
