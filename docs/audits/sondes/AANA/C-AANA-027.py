"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-027 (audit analyse du 05/10, §6) : une Idempotency-Key de 300 caractères créait le lead puis échouait en 500.
"""
SONDE = {
    'constat': 'C-AANA-027',
    'sha': '5908d43bb',
    'attendu': "défaut absent : POST leads-write avec une Idempotency-Key de 300 caractères répond 400 et ne crée aucun lead",
}


def sonde(ctx):
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.publicapi.models import ApiKey, IdempotencyRecord
    from apps.publicapi.portees import SCOPE_WRITE_LEADS
    co = Company.objects.create(nom='Sonde 027', slug='sonde-aana-027')
    _c, brute = ApiKey.issue(company=co, label='ecriture', scopes=[SCOPE_WRITE_LEADS])
    api = APIClient(raise_request_exception=False)
    api.credentials(HTTP_AUTHORIZATION='Api-Key %s' % brute)
    statut = exc = None
    try:
        with transaction.atomic():  # savepoint : un 500 base cassée ne contamine pas la sonde
            r = api.post('/api/public/v1/leads-write/', {'nom': 'Trop long'}, format='json',
                         HTTP_IDEMPOTENCY_KEY='k' * 300, HTTP_HOST='localhost')
            statut = r.status_code
    except Exception as e:  # noqa: BLE001
        exc = type(e).__name__
    leads = Lead.objects.filter(company=co).count()
    recs = IdempotencyRecord.objects.count()
    print('statut=%s exception=%s leads=%s enregistrements_idempotence=%s' % (statut, exc, leads, recs))
    return {'repro': statut == 400 and leads == 0 and recs == 0, 'statut': statut, 'leads': leads, 'exception': exc}
