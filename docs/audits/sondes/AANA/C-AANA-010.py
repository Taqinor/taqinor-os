"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-010 (audit analyse du 05/10, §6) : une clé read:stock lisait le job d'export leads d'une autre clé.
"""
SONDE = {
    'constat': 'C-AANA-010',
    'sha': '5908d43bb',
    'attendu': "défaut absent : une clé read:stock de la même société obtient 404 sur le job d'export leads (créateur : 200)",
}


def sonde(ctx):
    from unittest import mock
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.publicapi.models import ApiKey, BulkJob
    from apps.publicapi.portees import SCOPE_READ_LEADS, SCOPE_READ_STOCK
    from apps.records import storage
    co = Company.objects.create(nom='Sonde 010', slug='sonde-aana-010')
    cle_l, br_l = ApiKey.issue(company=co, label='leads', scopes=[SCOPE_READ_LEADS])
    cle_s, br_s = ApiKey.issue(company=co, label='stock', scopes=[SCOPE_READ_STOCK])
    job = BulkJob.objects.create(company=co, api_key=cle_l, type=BulkJob.TYPE_EXPORT, entite='leads',
                                 params={}, statut=BulkJob.STATUT_TERMINE,
                                 resultat_file_key='exports/sonde010/leads.csv')

    def get(brute):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION='Api-Key %s' % brute)
        with mock.patch.object(storage, 'get_minio_client') as cl:
            cl.return_value.generate_presigned_url.return_value = 'https://minio.example.test/leads.csv'
            return api.get('/api/public/v1/jobs/%s/' % job.id, HTTP_HOST='localhost')
    autre, crea = get(br_s), get(br_l)
    fuite = 'minio.example.test' in autre.content.decode('utf-8')
    print('autre cle=%s createur=%s fuite_lien=%s' % (autre.status_code, crea.status_code, fuite))
    return {'repro': autre.status_code == 404 and crea.status_code == 200 and not fuite,
            'autre': autre.status_code, 'createur': crea.status_code}
