# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K03 — Portée CRM à la création : A (Commercial, portée propriétaire) ne voit pas le lead de B
(`GET crm/leads/<id>/` = 404). Il POSTe `calepinage/calepinages/depuis-lead/ {lead}` et `calepinages/ {lead}`
sur des leads de B : la création résout le lead par `crm.selectors.get_company_lead` (société seule), jamais par
`leads_visibles` (ADVS44). Puis `GET calepinages/<id>/` sert le nom, la ville, l'adresse et le GPS du lead.
Oracle d'existence : un lead absent rend 404, un lead hors portée rend autre chose. Témoin : A sur SON lead => 201.
Réglage `vue_restreinte_au_responsable` laissé au défaut (éteint)."""
SONDE = {"constat": "C-ACON-003", "sha": "33cba7f5d",
         "attendu": "repro si A reçoit 404 sur crm/leads/<lead de B> mais 201 sur depuis-lead et sur calepinages/ "
                    "pour des leads de B, puis le détail rend adresse/ville/pin du lead de B ; lead absent => 404",
         "modeles": ["calepinage.Calepinage", "crm.Lead"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 003', slug='sonde-acon-003')
    role = Role.objects.create(company=co, nom='Commercial K03', permissions=list(COMMERCIAL_PERMISSIONS))
    U = get_user_model()
    a = U.objects.create_user(username='sonde_acon_003_a', password='x', company=co, role=role)
    b = U.objects.create_user(username='sonde_acon_003_b', password='x', company=co, role=role)
    api_a = APIClient()
    api_a.force_authenticate(a)

    def lead(owner, n):
        return Lead.objects.create(company=co, nom='Collegue', prenom=f'K03-{n}', owner=owner,
                                   email=f'k03-{n}@example.invalid', telephone=f'+21260000{n:04d}',
                                   ville='Rabat', adresse='12 rue des Orangers', gps_lat=33.9716, gps_lng=-6.8498)
    lb1, lb2, la = lead(b, 1), lead(b, 2), lead(a, 3)
    perms = {'calepinage_gerer': 'calepinage_gerer' in COMMERCIAL_PERMISSIONS,
             'calepinage_voir': 'calepinage_voir' in COMMERCIAL_PERMISSIONS}
    crm_b = api_a.get(f'/api/django/crm/leads/{lb1.pk}/', **H).status_code
    crm_a = api_a.get(f'/api/django/crm/leads/{la.pk}/', **H).status_code
    base = '/api/django/calepinage/calepinages/'
    dl = api_a.post(f'{base}depuis-lead/', {'lead': lb1.pk}, format='json', **H)
    cr = api_a.post(base, {'lead': lb2.pk, 'titre': 'K03'}, format='json', **H)
    absent = api_a.post(f'{base}depuis-lead/', {'lead': lb2.pk + 999999}, format='json', **H)
    temoin = api_a.post(f'{base}depuis-lead/', {'lead': la.pk}, format='json', **H)
    detail = None
    if dl.status_code in (200, 201):
        d = api_a.get(f"{base}{dl.data['calepinage']}/", **H)
        cg = (d.data or {}).get('contexte_geographique') or {}
        detail = {'http': d.status_code, 'lead': (d.data or {}).get('lead'),
                  'adresse': cg.get('adresse'), 'ville': cg.get('ville'), 'pin': cg.get('pin')}
    obs = {'perms_commercial': perms, 'crm_lead_de_B_http': crm_b, 'crm_lead_de_A_http': crm_a,
           'depuis_lead_lead_B_http': dl.status_code, 'depuis_lead_corps': str(dl.data)[:160],
           'create_lead_B_http': cr.status_code, 'create_corps': str(cr.data)[:120],
           'lead_absent_http': absent.status_code, 'temoin_lead_A_http': temoin.status_code,
           'detail_calepinage_lead_B': detail}
    temoin_ok = crm_a == 200 and temoin.status_code == 201 and absent.status_code == 404
    defaut = (crm_b == 404 and dl.status_code == 201 and cr.status_code == 201 and detail is not None
              and detail['http'] == 200 and detail['adresse'] and detail['pin'])
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    print(obs)
    return obs
