"""SOLMVP — coquille de migrations de l'app « contrats ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app contrats`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate contrats 0057_ntdoc18_obligation_preuve`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0057_ntdoc18_obligation_preuve'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AbonnementAddOnLigne'),
                migrations.DeleteModel(name='AlerteContrat'),
                migrations.DeleteModel(name='Avenant'),
                migrations.DeleteModel(name='Caution'),
                migrations.DeleteModel(name='CautionLocationLog'),
                migrations.DeleteModel(name='ClauseContrat'),
                migrations.DeleteModel(name='CommentaireRedline'),
                migrations.DeleteModel(name='CompteurUsage'),
                migrations.DeleteModel(name='CompteurUsageArchive'),
                migrations.DeleteModel(name='ContratActivity'),
                migrations.DeleteModel(name='ContratLien'),
                migrations.DeleteModel(name='CycleFacturationLog'),
                migrations.DeleteModel(name='EngagementSLA'),
                migrations.DeleteModel(name='EssaiAbonnement'),
                migrations.DeleteModel(name='EtapeApprobation'),
                migrations.DeleteModel(name='EtapeDunningLog'),
                migrations.DeleteModel(name='IndexationPrix'),
                migrations.DeleteModel(name='LigneEcheance'),
                migrations.DeleteModel(name='MetriquesSaasCache'),
                migrations.DeleteModel(name='ModeleContratClause'),
                migrations.DeleteModel(name='Obligation'),
                migrations.DeleteModel(name='PalierUsage'),
                migrations.DeleteModel(name='ParametreRenouvellement'),
                migrations.DeleteModel(name='ParametresAbonnement'),
                migrations.DeleteModel(name='ParametresCLM'),
                migrations.DeleteModel(name='ParametresLocation'),
                migrations.DeleteModel(name='PartieContrat'),
                migrations.DeleteModel(name='PieceConformite'),
                migrations.DeleteModel(name='Resiliation'),
                migrations.DeleteModel(name='RetenueGarantie'),
                migrations.DeleteModel(name='SignatureContrat'),
                migrations.DeleteModel(name='AddOnAbonnement'),
                migrations.DeleteModel(name='Clause'),
                migrations.DeleteModel(name='DocumentContrepartie'),
                migrations.DeleteModel(name='EcheancierContrat'),
                migrations.DeleteModel(name='EtapeDunning'),
                migrations.DeleteModel(name='JalonContrat'),
                migrations.DeleteModel(name='MotifResiliation'),
                migrations.DeleteModel(name='OrdreLocation'),
                migrations.DeleteModel(name='RegleApprobation'),
                migrations.DeleteModel(name='VersionContrat'),
                migrations.DeleteModel(name='LienDepotContrepartie'),
                migrations.DeleteModel(name='Contrat'),
                migrations.DeleteModel(name='ModeleContrat'),
                migrations.DeleteModel(name='PlanAbonnement'),
                migrations.DeleteModel(name='SequenceDunning'),
                migrations.DeleteModel(name='PlanRecurrent'),
            ],
            database_operations=[],
        ),
    ]
