"""SOLMVP — coquille de migrations de l'app « grc ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app grc`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate grc 0021_ntgrc35_sous_traitant_rgpd`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('grc', '0021_ntgrc35_sous_traitant_rgpd'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AnalyseImpactDPIA'),
                migrations.DeleteModel(name='AttestationPolitique'),
                migrations.DeleteModel(name='DeficienceControle'),
                migrations.DeleteModel(name='ExigenceCadre'),
                migrations.DeleteModel(name='FluxDonnees'),
                migrations.DeleteModel(name='IncidentSecurite'),
                migrations.DeleteModel(name='JournalDestruction'),
                migrations.DeleteModel(name='LegalHold'),
                migrations.DeleteModel(name='ModeleQuestionnaire'),
                migrations.DeleteModel(name='PlanTraitementRisque'),
                migrations.DeleteModel(name='PolitiqueRetentionObjet'),
                migrations.DeleteModel(name='PolitiqueVersion'),
                migrations.DeleteModel(name='ReponseQuestionnaire'),
                migrations.DeleteModel(name='RevueRisque'),
                migrations.DeleteModel(name='SousTraitantRGPD'),
                migrations.DeleteModel(name='ViolationDonnees'),
                migrations.DeleteModel(name='CadreConformite'),
                migrations.DeleteModel(name='PolitiqueInterne'),
                migrations.DeleteModel(name='QuestionnaireFournisseur'),
                migrations.DeleteModel(name='TestControle'),
                migrations.DeleteModel(name='ControleInterne'),
                migrations.DeleteModel(name='RisqueEntreprise'),
            ],
            database_operations=[],
        ),
    ]
