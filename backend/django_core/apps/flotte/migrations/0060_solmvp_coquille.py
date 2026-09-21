"""SOLMVP — coquille de migrations de l'app « flotte ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app flotte`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate flotte 0059_assurancevehicule_attestation_filename_and_more`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flotte', '0059_assurancevehicule_attestation_filename_and_more'),
        ('education', '0021_solmvp_coquille'),
        ('stock', '0159_solmvp12_detacher_flotte_qhse_rh'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AccuseCharte'),
                migrations.DeleteModel(name='ActiviteFlotte'),
                migrations.DeleteModel(name='AffectationConducteur'),
                migrations.DeleteModel(name='BaremeVignette'),
                migrations.DeleteModel(name='BudgetFlotte'),
                migrations.DeleteModel(name='CarteCarburant'),
                migrations.DeleteModel(name='CarteGriseVehicule'),
                migrations.DeleteModel(name='CharteVehicule'),
                migrations.DeleteModel(name='CoutVehicule'),
                migrations.DeleteModel(name='DemandeVehicule'),
                migrations.DeleteModel(name='EcheanceContrat'),
                migrations.DeleteModel(name='EcheanceReglementaire'),
                migrations.DeleteModel(name='EtatDesLieux'),
                migrations.DeleteModel(name='GarantieFlotte'),
                migrations.DeleteModel(name='Infraction'),
                migrations.DeleteModel(name='InspectionVehicule'),
                migrations.DeleteModel(name='JournalStatutVehicule'),
                migrations.DeleteModel(name='ParametreAmortissementCGI'),
                migrations.DeleteModel(name='ParametreApprobationOR'),
                migrations.DeleteModel(name='ParametreRemplacementFlotte'),
                migrations.DeleteModel(name='PieceFlotte'),
                migrations.DeleteModel(name='PleinCarburant'),
                migrations.DeleteModel(name='Pneumatique'),
                migrations.DeleteModel(name='RappelConstructeur'),
                migrations.DeleteModel(name='RemiseAccessoire'),
                migrations.DeleteModel(name='SignalementVehicule'),
                migrations.DeleteModel(name='Sinistre'),
                migrations.DeleteModel(name='TrajetChantier'),
                migrations.DeleteModel(name='TrajetTelematique'),
                migrations.DeleteModel(name='VisiteTechnique'),
                migrations.DeleteModel(name='ZoneGeographique'),
                migrations.DeleteModel(name='AssuranceVehicule'),
                migrations.DeleteModel(name='ContratVehicule'),
                migrations.DeleteModel(name='ModeleInspection'),
                migrations.DeleteModel(name='OrdreReparation'),
                migrations.DeleteModel(name='ReleveTelematique'),
                migrations.DeleteModel(name='ReservationVehicule'),
                migrations.DeleteModel(name='Conducteur'),
                migrations.DeleteModel(name='EcheanceEntretien'),
                migrations.DeleteModel(name='Garage'),
                migrations.DeleteModel(name='ReferentielFlotte'),
                migrations.DeleteModel(name='PlanEntretien'),
                migrations.DeleteModel(name='ActifFlotte'),
                migrations.DeleteModel(name='EnginRoulant'),
                migrations.DeleteModel(name='Vehicule'),
                migrations.DeleteModel(name='ModeleVehicule'),
            ],
            database_operations=[],
        ),
    ]
