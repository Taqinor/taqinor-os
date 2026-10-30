"""Sonde AANA50 : rejoue C-AANA-014 (audit analyse du 05/10, O7) : un utilisateur à portée équipe/propre notait, via la file hors-ligne
(`crm.lead.noter`), le lead d'un autre commercial qu'il ne voit pas en ligne (status applied, notes 0->1)."""
SONDE = {
    'constat': 'C-AANA-014',
    'sha': '5908d43bb',
    'attendu': "défaut absent : l'op crm.lead.noter sur le lead d'un autre commercial renvoie status error, aucune note créée",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead, LeadActivity
    from apps.roles.models import Role
    from apps.roles.permissions_registre import SCOPE_TEAM
    U = get_user_model()
    co = Company.objects.create(nom='Sonde 014', slug='sonde-aana-014')
    role = Role.objects.create(company=co, nom='commercial-equipe', permissions=['crm_voir', 'crm_modifier', SCOPE_TEAM])
    chef = U.objects.create_user(username='sonde-aana-014-c', password='x', company=co, role_legacy='responsable')
    moi = U.objects.create_user(username='sonde-aana-014-m', password='x', company=co, role_legacy='normal', role=role)
    autre = U.objects.create_user(username='sonde-aana-014-a', password='x', company=co, role_legacy='normal', role=role, supervisor=chef)
    lead = Lead.objects.create(company=co, nom='Autre', owner=autre)
    api = APIClient()
    api.force_authenticate(moi)
    op = {'client_op_id': 'sonde-014', 'op_type': 'crm.lead.noter', 'payload': {'lead': lead.id, 'body': 'intrusion'}}
    r = api.post('/api/django/offlinesync/operations/batch/', {'ops': [op]}, format='json', HTTP_HOST='localhost')
    statut = r.data['results'][0]['status'] if r.status_code == 200 else r.status_code
    notes = LeadActivity.objects.filter(lead=lead).count()
    print('crm.lead.noter hors portée -> status=%s notes=%s' % (statut, notes))
    return {'repro': statut == 'error' and notes == 0, 'status': statut, 'notes': notes}
