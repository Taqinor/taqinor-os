# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K61 (+ volet médiathèque de K42) — `GET records/attachments/all/` (IsAnyRole, `_scoped` société seul)
n'applique pas `_sans_leads_hors_portee` qu'ACVI6 a posé sur `AttachmentViewSet.get_queryset` : un Commercial
« soi » liste les pièces (nom de fichier, object_id, auteur) des leads d'un collègue, Admin RH et Commercial
terrain (sans crm_voir) celles de tous les leads. Témoins : `records/attachments/` sans cible et
`?model=crm.lead&id=` (filtrés), fiche lead du collègue (404/403). Rôles système semés comme `init_roles`,
connexion /api/django/token/. Pièce d'un lead de B jamais listée (contre-épreuve)."""
SONDE = {"constat": "C-APFS-023", "sha": "c9e72d5b2",
         "attendu": "repro si attachments/all/?model=crm.lead contient la pièce du lead de C1 pour C2 « soi » / "
                    "Admin RH / Commercial terrain alors que records/attachments/ (témoin ACVI6) ne la contient pas",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Lead", "records.Attachment"]}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Lead
    from apps.records.models import Attachment
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS023 {tag}', slug=f'sonde-apfs023-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS023-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS023-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    c1, _ = compte(A, 'Commercial', 'apfs023-c1')
    c2, api_c2 = compte(A, 'Commercial', 'apfs023-c2')
    _, api_rh = compte(A, 'Admin RH', 'apfs023-rh')
    _, api_ter = compte(A, 'Commercial terrain', 'apfs023-terrain')
    ct = ContentType.objects.get(app_label='crm', model='lead')
    lead1 = Lead.objects.create(company=A, nom='Tazi023', telephone='0661023001', owner=c1)
    p1 = Attachment.objects.create(company=A, content_type=ct, object_id=lead1.id, file_key='sonde/apfs023-cin.pdf',
                                   filename='CIN-Tazi023.pdf', size=10, mime='application/pdf', uploaded_by=c1)
    leadB = Lead.objects.create(company=B, nom='LeadB023', telephone='0661023999')
    pB = Attachment.objects.create(company=B, content_type=ct, object_id=leadB.id, file_key='sonde/apfs023-b.pdf',
                                   filename='B.pdf', size=10, mime='application/pdf')

    def ids(r):
        try:
            d = r.json()
        except Exception:
            return []
        lst = d if isinstance(d, list) else (d.get('results') or [])
        return [x.get('id') for x in lst if isinstance(x, dict)]

    out = {}
    for nom, a in (('c2_soi', api_c2), ('rh', api_rh), ('terrain', api_ter)):
        r_fiche = a.get(f'/api/django/crm/leads/{lead1.id}/', **H).status_code
        r_t1 = a.get('/api/django/records/attachments/', **H)
        r_t2 = a.get(f'/api/django/records/attachments/?model=crm.lead&id={lead1.id}', **H)
        r_all = a.get('/api/django/records/attachments/all/?model=crm.lead', **H)
        r_all2 = a.get('/api/django/records/attachments/all/', **H)
        champs = None
        for x in (r_all.json().get('results') or []) if r_all.status_code == 200 else []:
            if x.get('id') == p1.id:
                champs = {k: x.get(k) for k in ('filename', 'object_id') if k in x}
        out[nom] = {'fiche_lead_c1': r_fiche,
                    'temoin_liste_sans_cible': [r_t1.status_code, p1.id in ids(r_t1)],
                    'temoin_liste_cible': [r_t2.status_code, p1.id in ids(r_t2)],
                    'all_model_lead': [r_all.status_code, p1.id in ids(r_all), pB.id in ids(r_all)],
                    'all_sans_filtre': [r_all2.status_code, p1.id in ids(r_all2)],
                    'champs_exposes': champs}
    ecarts = [n for n, o in out.items() if o['fiche_lead_c1'] in (403, 404)
              and not o['temoin_liste_sans_cible'][1] and o['all_model_lead'][:2] == [200, True]]
    out['ecarts'] = ecarts
    out['fuite_B'] = any(o['all_model_lead'][2] for o in out.values() if isinstance(o, dict) and 'all_model_lead' in o)
    return {'repro': bool(ecarts), 'observe': out}
