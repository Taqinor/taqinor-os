"""SOLMVP — coquille de migrations de l'app « btp_chantier ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app btp_chantier`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate btp_chantier 0014_ntcon37_relance_visas`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('btp_chantier', '0014_ntcon37_relance_visas'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AbonnementRapportPhoto'),
                migrations.DeleteModel(name='AvenantChantier'),
                migrations.DeleteModel(name='DecompteGeneral'),
                migrations.DeleteModel(name='DiffusionPlan'),
                migrations.DeleteModel(name='JournalChantier'),
                migrations.DeleteModel(name='LotChecklistItem'),
                migrations.DeleteModel(name='LotTache'),
                migrations.DeleteModel(name='PPSPSSignature'),
                migrations.DeleteModel(name='ParametresBtpChantier'),
                migrations.DeleteModel(name='RFIReponse'),
                migrations.DeleteModel(name='ReserveChantierHistorique'),
                migrations.DeleteModel(name='SignatureBtp'),
                migrations.DeleteModel(name='VisaDocument'),
                migrations.DeleteModel(name='PPSPSChantier'),
                migrations.DeleteModel(name='RFI'),
                migrations.DeleteModel(name='ReserveChantier'),
                migrations.DeleteModel(name='Lot'),
            ],
            database_operations=[],
        ),
    ]
