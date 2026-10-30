"""Sonde AANA50 : rejoue C-AANA-023 (audit analyse du 05/10, O5) : une op hors-ligne `visite.mesures` écrasait la mesure bureau
(`applied 20->9`) sans comparer la version de base. ATTEND AANA40 + AANA42 (non construites : [BLOCKED])."""
SONDE = {
    'constat': 'C-AANA-023',
    'sha': '5908d43bb',
    'attendu': "défaut absent : op longueur_m=9 avec base antérieure -> status conflict, valeur bureau 20 intacte (ATTEND AANA40/AANA42 : défaut encore présent attendu)",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    co = Company.objects.create(nom='Sonde 023', slug='sonde-aana-023')
    role = Role.objects.create(company=co, nom='terrain', permissions=['visites_voir', 'visites_creer', 'visites_modifier'])
    u = U.objects.create_user(username='sonde-aana-023', password='x', company=co, role_legacy='normal', role=role)
    lead = Lead.objects.create(company=co, nom='Alaoui')
    v = VisiteTerrain.objects.create(company=co, lead=lead, commercial=u, mesures={'toiture': {'longueur_m': 20}})
    api = APIClient()
    api.force_authenticate(u)
    op = {'client_op_id': 'sonde-023', 'op_type': 'visite.mesures', 'payload': {
        'visite': v.id, 'categorie': 'toiture', 'valeurs': {'longueur_m': 9}, 'base_updated_at': '2020-01-01T00:00:00Z'}}
    r = api.post('/api/django/offlinesync/operations/batch/', {'ops': [op]}, format='json', HTTP_HOST='localhost')
    statut = r.data['results'][0]['status'] if r.status_code == 200 else r.status_code
    v.refresh_from_db()
    val = v.mesures.get('toiture', {}).get('longueur_m')
    print('visite.mesures base antérieure -> status=%s longueur_m bureau 20 -> %s (%s)' % (statut, val, 'conflit détecté' if statut == 'conflict' else 'ATTEND AANA40/AANA42 : défaut encore présent'))
    return {'repro': statut == 'conflict' and val == 20, 'status': statut, 'longueur_m': val, 'note': 'attend AANA40/AANA42'}
