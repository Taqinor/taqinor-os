# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K01 + K40 (même mécanisme) : un `IsAuthenticated` DRF EXPLICITE écrase le défaut `IsAuthenticatedInterne` (ASEC51) ;
un compte PORTAIL client (provisionné par le vrai service, mot de passe temporaire NON changé, connecté par la vraie
route /api/django/token/ → cookie JWT) lit les données internes de SA société par l'explorateur de données
(saved-queries/run, run sauvegardée, tableau de bord `donnees`, classeur `evaluer`), la corbeille et les paiements en
ligne. Témoins : GET crm/leads/ (défaut ASEC51) → 403 ; GET portail/mes-factures/ (garde IsPortal* + AUD139) → 403
mot de passe à changer. Contre-épreuve : aucune ligne de la société B. Annexe K60 : claims du jeton portail (company_id,
token_type, pas de portée) = tout ce que lit `fastapi_ia/app/core/security.py::verify_token`."""
SONDE = {"constat": "C-APFS-001", "sha": "c9e72d5b2",
         "attendu": "repro si le compte portail (must_change_password=True) obtient 200 + lignes de A sur "
                    "saved-queries/run (crm_leads nom/telephone/email, crm_clients ice/adresse, ventes_factures montants), "
                    "dashboards/<id>/donnees, classeurs/<id>/evaluer, corbeille, paiements-en-ligne ; alors que "
                    "crm/leads/ = 403 et portail/mes-factures/ = 403 ; aucune ligne de B",
         "modeles": ["authentication.CustomUser", "crm.Lead", "crm.Client", "ventes.Facture", "core.SavedQuery",
                     "core.Dashboard", "reporting.Classeur", "core.DeletionRecord", "core.PaymentTransaction"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.core import mail
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.crm.models import Client, Lead
    from apps.ventes.models import Facture
    from apps.portail.services import provisionner_compte_portail_client
    from core.models import DeletionRecord, PaymentTransaction
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    today = timezone.now().date()
    mail.outbox = []

    def societe(tag, montant):
        co = Company.objects.create(nom=f'Sonde APFS001 {tag}', slug=f'sonde-apfs001-{tag.lower()}')
        cl = Client.objects.create(company=co, nom=f'Client{tag}', prenom='APFS', email=f'apfs001{tag.lower()}@sonde.invalid',
                                   telephone=f'06000001{tag}0'[:10], ice=f'00000000000{tag}', adresse=f'Rue {tag}')
        ld = Lead.objects.create(company=co, nom=f'Prospect{tag}APFS', telephone=f'06110011{tag}0'[:10],
                                 email=f'prospect{tag.lower()}@sonde.invalid')
        fa = Facture.objects.create(company=co, reference=f'FAC-APFS001-{tag}', client=cl, statut='emise',
                                    taux_tva=Decimal('20'), montant_ht=Decimal(montant), montant_tva=Decimal(montant) / 5,
                                    montant_ttc=Decimal(montant) * Decimal('1.2'), date_emission=today)
        DeletionRecord.objects.create(company=co, content_type=ContentType.objects.get_for_model(Lead), object_id=ld.id,
                                      label=f'Lead supprimé {tag} APFS')
        PaymentTransaction.objects.create(company=co, content_type=ContentType.objects.get_for_model(Facture),
                                          object_id=fa.id, montant=Decimal(montant))
        return co, cl, ld, fa

    A, clA, ldA, faA = societe('A', '10000')
    B, clB, ldB, faB = societe('B', '77777')
    out = {}
    portail, cree = provisionner_compte_portail_client(A, clA.id)
    out['provision'] = {'cree': cree, 'portee': portail.portee, 'company_A': portail.company_id == A.id,
                        'must_change_password': portail.must_change_password, 'mails': len(mail.outbox)}
    mdp = None
    for m in mail.outbox:
        corps = m.body or ''
        trouve = re.search(r'(?i)mot de passe[^:\n]*:\s*(\S+)', corps)
        if trouve:
            mdp = trouve.group(1).strip()
    out['mdp_temporaire_lu_dans_le_mail'] = bool(mdp)
    if not mdp:  # repli : le mail n'a pas été lu (gabarit), même état de compte (drapeau intact)
        mdp = 'Temp-APFS001-x9'
        portail.set_password(mdp)
        portail.save(update_fields=['password'])
    api = APIClient()
    with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
        r = api.post('/api/django/token/', {'username': portail.username, 'password': mdp}, format='json', **H)
    out['login'] = r.status_code
    jeton = api.cookies.get('access_token')
    claims = {}
    if jeton is not None:
        from rest_framework_simplejwt.tokens import AccessToken
        p = AccessToken(jeton.value).payload
        claims = {'token_type': p.get('token_type'), 'company_id': p.get('company_id'),
                  'active_company_id': p.get('active_company_id'), 'cle_portee_presente': 'portee' in p,
                  'cles': sorted(p.keys())}
    out['K60_claims_jeton_portail'] = claims

    def rows_de(resp):
        try:
            return resp.json().get('rows') or []
        except Exception:
            return []

    def adhoc(dataset, select):
        rr = api.post('/api/django/core/saved-queries/run/', {'dataset': dataset, 'spec': {'select': select, 'limit': 5000}},
                      format='json', **H)
        rows = rows_de(rr)
        return rr.status_code, rows

    obs = {}
    s, rows = adhoc('crm_leads', ['nom', 'telephone', 'email'])
    obs['run_crm_leads'] = {'http': s, 'n': len(rows), 'A_vu': any(x.get('nom') == ldA.nom for x in rows),
                            'B_vu': any(x.get('nom') == ldB.nom for x in rows), 'exemple': rows[:1]}
    s, rows = adhoc('crm_clients', ['nom', 'ice', 'adresse', 'telephone', 'email'])
    obs['run_crm_clients'] = {'http': s, 'n': len(rows), 'A_vu': any(x.get('ice') == clA.ice for x in rows),
                              'B_vu': any(x.get('ice') == clB.ice for x in rows), 'exemple': rows[:1]}
    s, rows = adhoc('ventes_factures', ['id', 'montant_ttc', 'reste_du', 'client'])
    obs['run_ventes_factures'] = {'http': s, 'n': len(rows), 'A_vu': any(x.get('id') == faA.id for x in rows),
                                  'B_vu': any(x.get('id') == faB.id for x in rows), 'exemple': rows[:1]}
    # requête SAUVEGARDÉE (création = écriture par le compte portail) + run
    r = api.post('/api/django/core/saved-queries/', {'titre': 'q', 'dataset': 'ventes_factures',
                                                     'spec': {'aggregates': [{'alias': 'ca', 'fn': 'sum', 'field': 'montant_ttc'}]}},
                 format='json', **H)
    sq_id = r.json().get('id') if r.status_code == 201 else None
    obs['saved_query_create'] = r.status_code
    if sq_id:
        rr = api.post(f'/api/django/core/saved-queries/{sq_id}/run/', {}, format='json', **H)
        obs['saved_query_run'] = {'http': rr.status_code, 'rows': rows_de(rr)}
    # tableau de bord + donnees
    r = api.post('/api/django/core/dashboards/', {'titre': 'd', 'layout': {'widgets': [
        {'id': 'w1', 'titre': 'leads', 'dataset': 'crm_leads', 'spec': {'select': ['nom', 'telephone']}}]}},
        format='json', **H)
    obs['dashboard_create'] = r.status_code
    if r.status_code == 201:
        rr = api.get(f"/api/django/core/dashboards/{r.json()['id']}/donnees/", **H)
        w = {}
        try:
            body = rr.json()
            ws = body.get('widgets') if isinstance(body, dict) else body
            w = (ws or [{}])[0] if isinstance(ws, list) else {}
        except Exception:
            pass
        wrows = w.get('rows') or []
        obs['dashboard_donnees'] = {'http': rr.status_code, 'n': len(wrows),
                                    'A_vu': any(x.get('nom') == ldA.nom for x in wrows),
                                    'B_vu': any(x.get('nom') == ldB.nom for x in wrows), 'erreur': w.get('erreur'),
                                    'brut': None if wrows else str(rr.content[:200])}
    # classeur lié à la requête sauvegardée + evaluer =SOMME(A1)
    if sq_id:
        r = api.post('/api/django/reporting/classeurs/', {'titre': 'c', 'cellules': {'A1': ''},
                                                          'liens': {'A1': {'saved_query_id': sq_id}}}, format='json', **H)
        obs['classeur_create'] = r.status_code
        if r.status_code == 201:
            rr = api.post(f"/api/django/reporting/classeurs/{r.json()['id']}/evaluer/", {'formule': '=SOMME(A1)'},
                          format='json', **H)
            obs['classeur_evaluer'] = {'http': rr.status_code, 'body': rr.json() if rr.status_code == 200 else str(rr.content[:150])}
    rr = api.get('/api/django/core/corbeille/', **H)
    try:
        corb = rr.json()
        corb = corb.get('results', corb) if isinstance(corb, dict) else corb
    except Exception:
        corb = []
    labels = [c.get('label') for c in corb if isinstance(c, dict)]
    obs['corbeille'] = {'http': rr.status_code, 'labels': labels}
    rr = api.get('/api/django/core/paiements-en-ligne/', **H)
    try:
        pt = rr.json()
        pt = pt.get('results', pt) if isinstance(pt, dict) else pt
    except Exception:
        pt = []
    obs['paiements_en_ligne'] = {'http': rr.status_code, 'montants': [p.get('montant') for p in pt if isinstance(p, dict)]}
    rr = api.get('/api/django/core/scheduled-exports/', **H)
    obs['scheduled_exports_list'] = rr.status_code
    # témoins
    t = {}
    t['crm_leads_defaut_ASEC51'] = api.get('/api/django/crm/leads/', **H).status_code
    rr = api.get('/api/django/portail/mes-factures/', **H)
    t['portail_mes_factures'] = {'http': rr.status_code, 'code': (rr.json() or {}).get('code') if rr.status_code == 403 else None}
    t['auth_me'] = api.get('/api/django/auth/me/', **H).status_code
    portail.refresh_from_db()
    t['must_change_password_toujours'] = portail.must_change_password
    out['portail'] = obs
    out['temoins'] = t
    lus = [obs['run_crm_leads'], obs['run_crm_clients'], obs['run_ventes_factures']]
    defaut = all(x['http'] == 200 and x['A_vu'] for x in lus)
    fuite_B = any(x.get('B_vu') for x in lus) or bool(obs.get('dashboard_donnees', {}).get('B_vu')) \
        or any('B APFS' in (l or '') for l in labels)
    temoins_ok = (out['login'] == 200 and t['crm_leads_defaut_ASEC51'] == 403 and t['portail_mes_factures']['http'] == 403
                  and t['must_change_password_toujours'] is True)
    out['fuite_societe_B'] = fuite_B
    out['temoins_ok'] = temoins_ok
    out['repro'] = bool(defaut and temoins_ok and not fuite_B)
    print(out)
    return out
