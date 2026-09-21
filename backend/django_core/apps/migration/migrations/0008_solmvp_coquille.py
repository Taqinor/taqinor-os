"""SOLMVP — coquille de migrations de l'app « migration ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app migration`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate migration 0007_ntmig6_dernier_chargement_debut_at`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('migration', '0007_ntmig6_dernier_chargement_debut_at'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='DeploiementPartenaire'),
                migrations.DeleteModel(name='ParcoursCertificationPartenaire'),
                migrations.DeleteModel(name='PlaybookInstance'),
                migrations.DeleteModel(name='RapportReconciliation'),
                migrations.DeleteModel(name='LotMigration'),
                migrations.DeleteModel(name='ProjetMigration'),
            ],
            database_operations=[],
        ),
    ]
