"""SOLMVP — coquille de migrations de l'app « marketing ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app marketing`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate marketing 0011_aud621_reponse_enquete_jeton_invite`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0011_aud621_reponse_enquete_jeton_invite'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AbonnementListe'),
                migrations.DeleteModel(name='AppelTelephonique'),
                migrations.DeleteModel(name='ApprobationEnvoiCampagne'),
                migrations.DeleteModel(name='ArcJourney'),
                migrations.DeleteModel(name='AvisClient'),
                migrations.DeleteModel(name='BlocContenu'),
                migrations.DeleteModel(name='ClicLien'),
                migrations.DeleteModel(name='CommunicationEvenement'),
                migrations.DeleteModel(name='DomaineEnvoi'),
                migrations.DeleteModel(name='EnqueteNPS'),
                migrations.DeleteModel(name='EnvoiCampagne'),
                migrations.DeleteModel(name='ExecutionEtapeSequence'),
                migrations.DeleteModel(name='InscriptionEvenement'),
                migrations.DeleteModel(name='MessageWhatsAppEntrant'),
                migrations.DeleteModel(name='ModeleJourney'),
                migrations.DeleteModel(name='MouvementFidelite'),
                migrations.DeleteModel(name='OuverturePartage'),
                migrations.DeleteModel(name='ParametresMarketing'),
                migrations.DeleteModel(name='PostSocial'),
                migrations.DeleteModel(name='QuestionEvenement'),
                migrations.DeleteModel(name='RebondSoft'),
                migrations.DeleteModel(name='RegleUpsell'),
                migrations.DeleteModel(name='RelanceDevisAbandonne'),
                migrations.DeleteModel(name='ReponseEnquete'),
                migrations.DeleteModel(name='ScoreMaturite'),
                migrations.DeleteModel(name='SegmentMarketing'),
                migrations.DeleteModel(name='StatutEngagementContact'),
                migrations.DeleteModel(name='SupportOffline'),
                migrations.DeleteModel(name='SuppressionMarketing'),
                migrations.DeleteModel(name='VariationScoreMaturite'),
                migrations.DeleteModel(name='VersionFormulaireIntake'),
                migrations.DeleteModel(name='BilletEvenement'),
                migrations.DeleteModel(name='CompteFidelite'),
                migrations.DeleteModel(name='Enquete'),
                migrations.DeleteModel(name='FormulaireIntake'),
                migrations.DeleteModel(name='InscriptionSequence'),
                migrations.DeleteModel(name='LienTrackee'),
                migrations.DeleteModel(name='Campagne'),
                migrations.DeleteModel(name='EtapeSequence'),
                migrations.DeleteModel(name='EvenementMarketing'),
                migrations.DeleteModel(name='NoeudJourney'),
                migrations.DeleteModel(name='ListeDiffusion'),
                migrations.DeleteModel(name='SequenceRelance'),
                migrations.DeleteModel(name='TypeEvenement'),
            ],
            database_operations=[],
        ),
    ]
