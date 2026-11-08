# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K65 — carte `GET reporting/geo/?types=lead` (`reporting/geo.py::geo_points`, IsAnyRole) : `Lead.objects.filter(
company)` sans portée ni droit ; renvoie nom + GPS (champ de LEAD_PII_FIELDS) de tous les leads. Admin RH,
Commercial terrain, Technicien (403 sur crm/leads/), Commercial « soi » (404 sur la fiche du collègue) et un rôle
personnalisé sans client_pii_voir reçoivent les coordonnées. Rôles système semés comme `init_roles`, connexion
/api/django/token/. Lead de B jamais présent (contre-épreuve)."""
SONDE = {"constat": "C-APFS-026", "sha": "c9e72d5b2",
         "attendu": "repro si geo/?types=lead rend le point (nom + lat/lng) du lead de C1 à rh/terrain/tech/c2 soi, "
                    "ou les coordonnées au rôle sans client_pii_voir ; lead de B absent",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Lead"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Lead
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS026 {tag}', slug=f'sonde-apfs026-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS026-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS026-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    perms_sans_pii = [c for c in dict(CANONICAL_SYSTEM_ROLES)['Commercial'] if c != 'client_pii_voir'
                      and not c.startswith('records_scope')]
    Role.objects.create(company=A, nom='Commercial sans PII 026', permissions=perms_sans_pii, est_systeme=False)
    c1, _ = compte(A, 'Commercial', 'apfs026-c1')
    lead = Lead.objects.create(company=A, nom='Alaoui026', telephone='0661026001', owner=c1,
                               gps_lat=Decimal('33.573110'), gps_lng=Decimal('-7.589843'))
    Lead.objects.create(company=B, nom='LeadB026', gps_lat=Decimal('34.0'), gps_lng=Decimal('-6.8'))
    out = {}
    for nom, role in (('rh', 'Admin RH'), ('terrain', 'Commercial terrain'), ('tech', 'Technicien'),
                      ('c2_soi', 'Commercial'), ('sans_pii', 'Commercial sans PII 026')):
        _, a = compte(A, role, f'apfs026-{nom}')
        o = {'ecran_leads': a.get('/api/django/crm/leads/', **H).status_code,
             'fiche_lead_c1': a.get(f'/api/django/crm/leads/{lead.id}/', **H).status_code}
        r = a.get('/api/django/reporting/geo/?types=lead', **H)
        pts = r.json().get('points', []) if r.status_code == 200 else []
        p = next((x for x in pts if x.get('id') == f'lead-{lead.id}'), None)
        o['geo'] = [r.status_code, p is not None, (p or {}).get('label'), (p or {}).get('lat'), (p or {}).get('lng'),
                    any((x.get('label') or '') == 'LeadB026' for x in pts)]
        out[nom] = o
    ecarts = [n for n in ('rh', 'terrain', 'tech', 'c2_soi')
              if out[n]['fiche_lead_c1'] in (403, 404) and out[n]['geo'][1]]
    if out['sans_pii']['geo'][1] and out['sans_pii']['geo'][3] is not None:
        ecarts.append('sans_pii:coordonnees')
    out['ecarts'] = ecarts
    out['fuite_B'] = any(o['geo'][5] for o in out.values() if isinstance(o, dict) and 'geo' in o)
    return {'repro': bool(ecarts), 'observe': out}
