"""SOLMVP — coquille de migrations de l'app « fpa ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app fpa`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate fpa 0001_initial`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fpa', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CommentaireVariance'),
                migrations.DeleteModel(name='HypotheseRecrutement'),
                migrations.DeleteModel(name='LignePrevisionGlissante'),
                migrations.DeleteModel(name='LigneScenario'),
                migrations.DeleteModel(name='MappingCategorieCompte'),
                migrations.DeleteModel(name='SoumissionBudgetDepartement'),
                migrations.DeleteModel(name='LigneBudgetDepartement'),
                migrations.DeleteModel(name='PrevisionGlissante'),
                migrations.DeleteModel(name='ScenarioBudgetaire'),
                migrations.DeleteModel(name='CycleBudgetaire'),
                migrations.DeleteModel(name='Departement'),
            ],
            database_operations=[],
        ),
    ]
