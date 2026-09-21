"""SOLMVP — coquille de migrations de l'app « sante ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app sante`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate sante 0020_ntsan24_acterealise_instruments_utilises`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sante', '0020_ntsan24_acterealise_instruments_utilises'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ActeRealise'),
                migrations.DeleteModel(name='GrilleTarifaire'),
                migrations.DeleteModel(name='HoraireOuverturePraticien'),
                migrations.DeleteModel(name='IndisponibilitePraticien'),
                migrations.DeleteModel(name='MotifConsultation'),
                migrations.DeleteModel(name='PaiementSante'),
                migrations.DeleteModel(name='ParametragePenaliteAnnulation'),
                migrations.DeleteModel(name='PraticienSite'),
                migrations.DeleteModel(name='ActeMedical'),
                migrations.DeleteModel(name='FactureSante'),
                migrations.DeleteModel(name='InstrumentSterilise'),
                migrations.DeleteModel(name='PriseEnCharge'),
                migrations.DeleteModel(name='Admission'),
                migrations.DeleteModel(name='CycleSterilisation'),
                migrations.DeleteModel(name='RendezVous'),
                migrations.DeleteModel(name='Patient'),
                migrations.DeleteModel(name='Praticien'),
                migrations.DeleteModel(name='Salle'),
                migrations.DeleteModel(name='Convention'),
            ],
            database_operations=[],
        ),
    ]
