# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K64 — omnibox `reporting/search/` et cloche `reporting/notifications/` (IsAnyRole) bornées à la société seule :
`_spec_lead` / `_spec_client` cherchent sur téléphone/email et les renvoient en `sublabel` ; aucune portée, aucun
`crm_voir`, aucun `client_pii_voir`. Commercial terrain / Admin RH (403 sur crm/leads/ = témoin), Commercial « soi »
(404 sur la fiche du collègue) retrouvent le lead d'un collègue par son numéro ; un rôle personnalisé `crm_voir`
SANS `client_pii_voir` voit le téléphone en clair ; la cloche liste les factures impayées avec nom du client à des
rôles sans ventes_voir. Rôles système semés comme `init_roles`, connexion /api/django/token/. B jamais présent."""
SONDE = {"constat": "C-APFS-025", "sha": "c9e72d5b2",
         "attendu": "repro si search/?q=<tel> rend le groupe lead (tel en sublabel) à terrain/rh/c2 soi, ou le tel "
                    "au rôle sans client_pii_voir ; ou notifications rend la facture impayée à terrain/rh",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Lead", "crm.Client", "facturation.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Client, Lead
    from apps.ventes.models import Facture
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    today = timezone.now().date()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS025 {tag}', slug=f'sonde-apfs025-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS025-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS025-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    # rôle personnalisé : les codes du Commercial MOINS client_pii_voir (prévu : code octroyable, registre l.758-761)
    perms_sans_pii = [c for c in dict(CANONICAL_SYSTEM_ROLES)['Commercial'] if c != 'client_pii_voir'
                      and not c.startswith('records_scope')]
    Role.objects.create(company=A, nom='Commercial sans PII 025', permissions=perms_sans_pii, est_systeme=False)
    c1, _ = compte(A, 'Commercial', 'apfs025-c1')
    _, api_c2 = compte(A, 'Commercial', 'apfs025-c2')
    _, api_ter = compte(A, 'Commercial terrain', 'apfs025-terrain')
    _, api_rh = compte(A, 'Admin RH', 'apfs025-rh')
    _, api_nopii = compte(A, 'Commercial sans PII 025', 'apfs025-nopii')
    TEL = '0661025777'
    lead = Lead.objects.create(company=A, nom='Bennani025', telephone=TEL, email='bennani025@sonde.invalid', owner=c1)
    Lead.objects.create(company=B, nom='Bennani025B', telephone=TEL)
    cl = Client.objects.create(company=A, nom='ClientImpaye025', email='impaye025@sonde.invalid', telephone='0661025888')
    Facture.objects.create(company=A, reference='FAC-APFS025-A', client=cl, statut='emise', taux_tva=Decimal('20'),
                           montant_ht=Decimal('1000'), montant_tva=Decimal('200'), montant_ttc=Decimal('1200'),
                           date_emission=today, date_echeance=today)

    out = {}
    for nom, a in (('terrain', api_ter), ('rh', api_rh), ('c2_soi', api_c2), ('sans_pii', api_nopii)):
        o = {'ecran_leads': a.get('/api/django/crm/leads/', **H).status_code,
             'fiche_lead_c1': a.get(f'/api/django/crm/leads/{lead.id}/', **H).status_code,
             'ecran_factures': a.get('/api/django/ventes/factures/', **H).status_code}
        r = a.get(f'/api/django/reporting/search/?q={TEL}', **H)
        groupes = r.json().get('groups', []) if r.status_code == 200 else []
        g_lead = [x for g in groupes if g.get('type') == 'lead' for x in g.get('results', [])]
        o['search_tel'] = [r.status_code, len(g_lead), any(TEL in (x.get('sublabel') or '') for x in g_lead),
                           any('Bennani025B' in (x.get('label') or '') for x in g_lead)]
        r = a.get('/api/django/reporting/search/?q=impaye025', **H)
        groupes = r.json().get('groups', []) if r.status_code == 200 else []
        g_cl = [x for g in groupes if g.get('type') == 'client' for x in g.get('results', [])]
        o['search_client'] = [r.status_code, len(g_cl), any('@' in (x.get('sublabel') or '') for x in g_cl)]
        r = a.get('/api/django/reporting/notifications/', **H)
        fac = r.json().get('factures_impayees') if r.status_code == 200 else None
        txt = str(fac)
        o['cloche_factures'] = [r.status_code, 'FAC-APFS025-A' in txt, 'ClientImpaye025' in txt]
        out[nom] = o
    ecarts = []
    for nom in ('terrain', 'rh', 'c2_soi'):
        o = out[nom]
        if o['fiche_lead_c1'] in (403, 404) and o['search_tel'][1] > 0:
            ecarts.append(f'{nom}:lead_par_tel(sublabel_tel={o["search_tel"][2]})')
    if out['sans_pii']['search_tel'][2] or out['sans_pii']['search_client'][2]:
        ecarts.append('sans_pii:tel/email en sublabel')
    for nom in ('terrain', 'rh'):
        o = out[nom]
        if o['ecran_factures'] in (403, 404) and o['cloche_factures'][1]:
            ecarts.append(f'{nom}:cloche_facture_impayee')
    out['ecarts'] = ecarts
    out['fuite_B'] = any(o['search_tel'][3] for o in out.values() if isinstance(o, dict) and 'search_tel' in o)
    return {'repro': bool(ecarts), 'observe': out}
