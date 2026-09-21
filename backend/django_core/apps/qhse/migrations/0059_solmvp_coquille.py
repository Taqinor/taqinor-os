"""SOLMVP — coquille de migrations de l'app « qhse ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app qhse`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate qhse 0058_sol2_ncr_cycle_sterilisation_sans_fk`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0058_sol2_ncr_cycle_sterilisation_sans_fk'),
        ('stock', '0159_solmvp12_detacher_flotte_qhse_rh'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='AccuseLecture'),
                migrations.DeleteModel(name='AnalyseNcr'),
                migrations.DeleteModel(name='AspectEnvironnemental'),
                migrations.DeleteModel(name='AuditCertification'),
                migrations.DeleteModel(name='AuditPlanifie'),
                migrations.DeleteModel(name='CauseIncident'),
                migrations.DeleteModel(name='CheckinSecurite'),
                migrations.DeleteModel(name='ClauseNorme'),
                migrations.DeleteModel(name='ConsignationLoto'),
                migrations.DeleteModel(name='ContactUrgence'),
                migrations.DeleteModel(name='ContexteOrganisation'),
                migrations.DeleteModel(name='ControleReception'),
                migrations.DeleteModel(name='DecisionReunion'),
                migrations.DeleteModel(name='DemandeActionFournisseur'),
                migrations.DeleteModel(name='DemandeChangementCapa'),
                migrations.DeleteModel(name='Derogation'),
                migrations.DeleteModel(name='ElementRappel'),
                migrations.DeleteModel(name='EtapeDeclarationAt'),
                migrations.DeleteModel(name='ExerciceUrgence'),
                migrations.DeleteModel(name='InductionSecurite'),
                migrations.DeleteModel(name='InspectionSecurite'),
                migrations.DeleteModel(name='ItemNotation'),
                migrations.DeleteModel(name='LigneBilanCarbone'),
                migrations.DeleteModel(name='LigneEvaluationRisque'),
                migrations.DeleteModel(name='ObservationSecurite'),
                migrations.DeleteModel(name='PartieInteressee'),
                migrations.DeleteModel(name='PointControleReception'),
                migrations.DeleteModel(name='QhseChatterEntry'),
                migrations.DeleteModel(name='RecyclageModule'),
                migrations.DeleteModel(name='ReleveConsommation'),
                migrations.DeleteModel(name='ReleveControle'),
                migrations.DeleteModel(name='ReleveCourbeIV'),
                migrations.DeleteModel(name='ReleveThermographie'),
                migrations.DeleteModel(name='ReponseCritere'),
                migrations.DeleteModel(name='RetourClientQualite'),
                migrations.DeleteModel(name='RevueObjectif'),
                migrations.DeleteModel(name='RevueVeilleReglementaire'),
                migrations.DeleteModel(name='RisqueOpportuniteCapa'),
                migrations.DeleteModel(name='Secouriste'),
                migrations.DeleteModel(name='SignalementPublic'),
                migrations.DeleteModel(name='ActionCorrectivePreventive'),
                migrations.DeleteModel(name='AnalyseIncident'),
                migrations.DeleteModel(name='Audit'),
                migrations.DeleteModel(name='BordereauSuiviDechet'),
                migrations.DeleteModel(name='CampagneRappel'),
                migrations.DeleteModel(name='Certification'),
                migrations.DeleteModel(name='CritereAudit'),
                migrations.DeleteModel(name='DeclarationCnss'),
                migrations.DeleteModel(name='DemandeChangement'),
                migrations.DeleteModel(name='DiffusionProcedure'),
                migrations.DeleteModel(name='LienSignalementPublic'),
                migrations.DeleteModel(name='NotationFinChantier'),
                migrations.DeleteModel(name='ObjectifQhse'),
                migrations.DeleteModel(name='PermisTravail'),
                migrations.DeleteModel(name='PlanControleReception'),
                migrations.DeleteModel(name='PlanInspectionChantier'),
                migrations.DeleteModel(name='PlanUrgence'),
                migrations.DeleteModel(name='PointControleModele'),
                migrations.DeleteModel(name='ProgrammeAudit'),
                migrations.DeleteModel(name='ReunionQhse'),
                migrations.DeleteModel(name='RisqueOpportunite'),
                migrations.DeleteModel(name='VeilleReglementaire'),
                migrations.DeleteModel(name='ConformiteEnvironnementale'),
                migrations.DeleteModel(name='Dechet'),
                migrations.DeleteModel(name='EvaluationRisque'),
                migrations.DeleteModel(name='GrilleAudit'),
                migrations.DeleteModel(name='Incident'),
                migrations.DeleteModel(name='IndicateurESG'),
                migrations.DeleteModel(name='NonConformite'),
                migrations.DeleteModel(name='PlanInspectionModele'),
                migrations.DeleteModel(name='ProcedureQualite'),
                migrations.DeleteModel(name='BilanCarbone'),
                migrations.DeleteModel(name='CodeDefaut'),
            ],
            database_operations=[],
        ),
    ]
