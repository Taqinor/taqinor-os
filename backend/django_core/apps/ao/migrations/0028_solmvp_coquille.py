"""SOLMVP — coquille de migrations de l'app « ao ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app ao`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate ao 0027_cal30_calepinage_id`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0027_cal30_calepinage_id'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CautionSoumission'),
                migrations.DeleteModel(name='CibleFinanciere'),
                migrations.DeleteModel(name='CitationPlanche'),
                migrations.DeleteModel(name='ControleCoherence'),
                migrations.DeleteModel(name='EcheanceAO'),
                migrations.DeleteModel(name='EquipementAO'),
                migrations.DeleteModel(name='ExigenceCPS'),
                migrations.DeleteModel(name='IdentiteAO'),
                migrations.DeleteModel(name='KitCalepinage'),
                migrations.DeleteModel(name='LigneChecklistPartenaire'),
                migrations.DeleteModel(name='LigneCoutRevient'),
                migrations.DeleteModel(name='ManifestePack'),
                migrations.DeleteModel(name='PieceAdministrative'),
                migrations.DeleteModel(name='PieceDossierAO'),
                migrations.DeleteModel(name='PieceModele'),
                migrations.DeleteModel(name='PlanSource'),
                migrations.DeleteModel(name='PlancheAO'),
                migrations.DeleteModel(name='QuestionAO'),
                migrations.DeleteModel(name='ResultatAO'),
                migrations.DeleteModel(name='SimulationRentabilite'),
                migrations.DeleteModel(name='ZoneAO'),
                migrations.DeleteModel(name='ArtefactAO'),
                migrations.DeleteModel(name='ChaineCotes'),
                migrations.DeleteModel(name='EconomieAO'),
                migrations.DeleteModel(name='LigneBordereau'),
                migrations.DeleteModel(name='ModelePack'),
                migrations.DeleteModel(name='ObstacleAO'),
                migrations.DeleteModel(name='PieceConsultation'),
                migrations.DeleteModel(name='PieceSoumission'),
                migrations.DeleteModel(name='SectionMemoire'),
                migrations.DeleteModel(name='SerieQuestions'),
                migrations.DeleteModel(name='DossierAO'),
                migrations.DeleteModel(name='DossierSoumission'),
                migrations.DeleteModel(name='ReleveAO'),
                migrations.DeleteModel(name='SectionBordereau'),
                migrations.DeleteModel(name='VarianteCalepinage'),
                migrations.DeleteModel(name='BordereauPrix'),
                migrations.DeleteModel(name='ToitureAO'),
                migrations.DeleteModel(name='BatimentAO'),
                migrations.DeleteModel(name='PresetCalepinage'),
                migrations.DeleteModel(name='AppelOffre'),
            ],
            database_operations=[],
        ),
    ]
