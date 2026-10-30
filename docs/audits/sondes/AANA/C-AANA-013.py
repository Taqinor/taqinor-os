"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-013 (audit analyse du 05/10, §6) : le pull CSV ?token= acceptait une clé portant un scope d'écriture.
"""
SONDE = {
    'constat': 'C-AANA-013',
    'sha': '5908d43bb',
    'attendu': "défaut absent : exports/leads.csv?token=<clé read:leads + leads:write> répond 403 (clé lecture seule : 200)",
}


def sonde(ctx):
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.publicapi.models import ApiKey
    from apps.publicapi.portees import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS
    co = Company.objects.create(nom='Sonde 013', slug='sonde-aana-013')
    Lead.objects.create(company=co, nom='Lead sonde 013')

    def pull(scopes):
        _c, brute = ApiKey.issue(company=co, label='tableur', scopes=scopes)
        return APIClient().get('/api/public/v1/exports/leads.csv?token=%s' % brute, HTTP_HOST='localhost')
    ecr, lec = pull([SCOPE_READ_LEADS, SCOPE_WRITE_LEADS]), pull([SCOPE_READ_LEADS])
    print('cle ecriture=%s cle lecture=%s' % (ecr.status_code, lec.status_code))
    return {'repro': ecr.status_code == 403 and lec.status_code == 200,
            'ecriture': ecr.status_code, 'lecture': lec.status_code}
