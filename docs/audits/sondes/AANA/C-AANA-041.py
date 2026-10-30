"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-041 (audit analyse du 05/10, §6) : l'API publique stockait un canal hors liste et un e-mail invalide (201).
"""
SONDE = {
    'constat': 'C-AANA-041',
    'sha': '5908d43bb',
    'attendu': "défaut absent : POST leads-write {nom:'X', canal:'nimporte', email:'pas-un-email'} répond 400 (champ fautif nommé) et ne crée aucun lead",
}


def sonde(ctx):
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.publicapi.models import ApiKey
    from apps.publicapi.portees import SCOPE_WRITE_LEADS
    co = Company.objects.create(nom='Sonde 041', slug='sonde-aana-041')
    _c, brute = ApiKey.issue(company=co, label='ecriture', scopes=[SCOPE_WRITE_LEADS])
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Api-Key %s' % brute)
    r = api.post('/api/public/v1/leads-write/', {'nom': 'X', 'canal': 'nimporte', 'email': 'pas-un-email'},
                 format='json', HTTP_HOST='localhost')
    leads = Lead.objects.filter(company=co).count()
    err = r.data.get('error', {}) if hasattr(r, 'data') and isinstance(r.data, dict) else {}
    print('statut=%s code=%s param=%s leads_crees=%s' % (r.status_code, err.get('code'), err.get('param'), leads))
    return {'repro': r.status_code == 400 and leads == 0 and err.get('param') in ('canal', 'email'),
            'statut': r.status_code, 'param': err.get('param'), 'leads': leads}
