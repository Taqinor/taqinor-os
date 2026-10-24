SONDE = {"constat": "C-APAR-VER-001", "sha": "b3c7e4065",
         "attendu": "un Responsable qui a démarré un workflow ne décide pas sa propre étape : POST approbations-en-attente/decider/ (source workflow) → 403 « séparation des tâches », étape toujours en attente"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from core import workflow as core_workflow
    from core.models import WorkflowDefinition, WorkflowStepDefinition, WorkflowStepInstance
    co = Company.objects.create(nom='Sonde APAR VER-001', slug='sonde-apar-ver-001')
    resp = get_user_model().objects.create_user(username='sonde-apar-ver-001-resp', password='x', company=co,
                                                role_legacy='responsable')
    wf = WorkflowDefinition.objects.create(company=co, code='sonde-apar-ver-001', nom='Sonde APAR')
    WorkflowStepDefinition.objects.create(definition=wf, ordre=1, nom='Palier 1')
    cible = Company.objects.create(nom='Cible sonde', slug='sonde-apar-ver-001-cible')
    instance = core_workflow.demarrer_workflow(wf, cible, co, user=resp)
    etape = core_workflow.etape_courante_de(instance)
    api = APIClient()
    api.force_authenticate(resp)
    r = api.post('/api/django/reporting/approbations-en-attente/decider/',
                 {'source': 'workflow', 'id': etape.pk, 'decision': 'approuver'}, format='json', HTTP_HOST='localhost')
    etape.refresh_from_db()
    champs_demandeur = [f.name for f in instance._meta.get_fields()
                        if f.name in ('demandeur', 'requested_by', 'created_by', 'initiateur', 'started_by')]
    print(f'demandeur enregistré sur WorkflowInstance : {champs_demandeur or "aucun champ"} ; décision du démarreur={r.status_code} '
          f'statut étape={etape.statut} (attendu 403, {WorkflowStepInstance.STATUT_EN_ATTENTE})')
    return {'repro': r.status_code == 200 and etape.statut != WorkflowStepInstance.STATUT_EN_ATTENTE,
            'decision': r.status_code, 'statut': etape.statut, 'champs_demandeur': champs_demandeur}
