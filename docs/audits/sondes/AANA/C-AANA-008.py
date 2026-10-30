"""Sonde AANA50 : rejoue C-AANA-008 (audit analyse du 05/10, AG4b) : un utilisateur SANS crm_creer postait
`/agent/logs/confirmer/ {action_key:'crm.client.create', object_id:<client existant>}` (201), puis l'annulation du journal par un admin
SUPPRIMAIT le client préexistant (`client_deleted=True`)."""
SONDE = {
    'constat': 'C-AANA-008',
    'sha': '5908d43bb',
    'attendu': "défaut absent : confirmer sans preuve valide = 403 et aucun journal ; annuler un journal pointant un client préexistant = 409 et le client existe encore",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.agent import services
    from apps.agent.models import AgentActionLog
    from apps.crm.models import Client
    from apps.roles.models import Role
    U = get_user_model()
    co = Company.objects.create(nom='Sonde 008', slug='sonde-aana-008')
    lecteur = U.objects.create_user(username='sonde-aana-008-l', password='x', company=co, role=Role.objects.create(company=co, nom='Lecture', permissions=['crm_voir']))
    admin = U.objects.create_user(username='sonde-aana-008-a', password='x', company=co, role_legacy='admin')
    agent = U.objects.create_user(username='sonde-aana-008-g', password='x', company=co)
    existant = Client.objects.create(company=co, nom='Client préexistant', created_by=admin)
    h = {'HTTP_HOST': 'localhost'}
    api = APIClient()
    api.force_authenticate(lecteur)
    r1 = api.post('/api/django/agent/logs/confirmer/', {'action_key': 'crm.client.create', 'risk_level': 'outward',
                  'inputs': {'nom': 'X'}, 'object_id': existant.id}, format='json', **h)
    logs = AgentActionLog.objects.filter(company=co).count()
    log = services.log_confirmed_action(company=co, user=agent, action_key='crm.client.create',
                                        risk_level=AgentActionLog.RiskLevel.OUTWARD, resulted_object=existant)
    adm = APIClient()
    adm.force_authenticate(admin)
    r2 = adm.post('/api/django/agent/logs/%s/annuler/' % log.pk, **h)
    supprime = not Client.objects.filter(pk=existant.pk).exists()
    print('confirmer sans crm_creer/preuve=%s journaux=%s | annuler journal sur client préexistant=%s client_deleted=%s' % (r1.status_code, logs, r2.status_code, supprime))
    return {'repro': r1.status_code == 403 and logs == 0 and r2.status_code == 409 and not supprime, 'confirmer': r1.status_code, 'journaux': logs, 'annuler': r2.status_code, 'client_deleted': supprime}
