# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K63 — `POST imports/export/<entity>/` (`dataimport/exports_view.py::export_list`, IsAnyRole) exporte en XLSX
factures / tickets / devis bornés à la société seule : ni `ventes_export`, ni `*_voir`, ni portée. Commercial
terrain et Admin RH (403 sur ventes/factures/ = témoin) obtiennent le classeur de TOUTES les factures avec le nom
des clients ; Viewer (ventes_voir sans ventes_export) aussi ; Commercial « soi » exporte le devis d'un collègue
(404 sur sa fiche). Rôles système semés comme `init_roles`, connexion /api/django/token/. B jamais présent."""
SONDE = {"constat": "C-APFS-024", "sha": "c9e72d5b2",
         "attendu": "repro si un rôle sans ventes_export (ou sans ventes_voir) reçoit 200 + un XLSX contenant la "
                    "facture/le client de A, ou si C2 « soi » exporte le devis de C1 ; aucune ligne de B",
         "modeles": ["authentication.CustomUser", "roles.Role", "crm.Client", "facturation.Facture", "ventes.Devis",
                     "sav.Ticket"]}


def sonde(ctx):
    import io
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES, SYSTEM_ROLE_PERIMETRES
    from apps.crm.models import Client
    from apps.ventes.models import Devis, Facture
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    today = timezone.now().date()

    def societe(tag):
        co = Company.objects.create(nom=f'Sonde APFS024 {tag}', slug=f'sonde-apfs024-{tag.lower()}')
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            r, _ = Role.objects.get_or_create(company=co, nom=nom,
                                              defaults={'permissions': list(perms), 'est_systeme': True})
            r.permissions, r.est_systeme, r.perimetre = list(perms), True, SYSTEM_ROLE_PERIMETRES.get(nom)
            r.save()
        return co

    def compte(co, nom_role, username):
        r = Role.objects.get(company=co, nom=nom_role)
        u = U.objects.create_user(username=username, password='Sonde-APFS024-x9', company=co, role=r,
                                  role_legacy=U.tier_for_role(r) or 'normal')
        a = APIClient()
        with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
            rr = a.post('/api/django/token/', {'username': username, 'password': 'Sonde-APFS024-x9'}, format='json', **H)
        assert rr.status_code == 200, (username, rr.status_code)
        return u, a

    A, B = societe('A'), societe('B')
    c1, _ = compte(A, 'Commercial', 'apfs024-c1')
    c2, api_c2 = compte(A, 'Commercial', 'apfs024-c2')
    _, api_ter = compte(A, 'Commercial terrain', 'apfs024-terrain')
    _, api_rh = compte(A, 'Admin RH', 'apfs024-rh')
    _, api_view = compte(A, 'Viewer', 'apfs024-viewer')
    _, api_dir = compte(A, 'Directeur', 'apfs024-dir')
    devis_c1 = None
    for co, tag in ((A, 'A'), (B, 'B')):
        cl = Client.objects.create(company=co, nom=f'ClientExport{tag}024', email=f'e{tag}024@sonde.invalid')
        Facture.objects.create(company=co, reference=f'FAC-APFS024-{tag}', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                               montant_ttc=Decimal('1200'), date_emission=today)
        d = Devis.objects.create(company=co, reference=f'DEV-APFS024-{tag}', client=cl,
                                 created_by=c1 if tag == 'A' else None)
        if tag == 'A':
            devis_c1 = d

    def lire(r):
        if r.status_code != 200:
            return None
        try:
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(r.content), read_only=True)
            vals = [str(c) for row in wb.active.iter_rows(values_only=True) for c in row if c is not None]
            return ' | '.join(vals)
        except Exception as e:
            return f'illisible {e!r}'[:80]

    out = {}
    for nom, a in (('terrain', api_ter), ('rh', api_rh), ('viewer', api_view), ('c2_soi', api_c2), ('directeur', api_dir)):
        o = {'ecran_factures': a.get('/api/django/ventes/factures/', **H).status_code,
             'ecran_devis_c1': a.get(f'/api/django/ventes/devis/{devis_c1.id}/', **H).status_code}
        r = a.post('/api/django/imports/export/factures/', {}, format='json', **H)
        t = lire(r) or ''
        o['export_factures'] = [r.status_code, 'FAC-APFS024-A' in t, 'ClientExportA024' in t, 'FAC-APFS024-B' in t]
        r = a.post('/api/django/imports/export/devis/', {'ids': [devis_c1.id]}, format='json', **H)
        t = lire(r) or ''
        o['export_devis_c1'] = [r.status_code, 'DEV-APFS024-A' in t]
        r = a.post('/api/django/imports/export/tickets/', {}, format='json', **H)
        o['export_tickets'] = r.status_code
        out[nom] = o
    ecarts = []
    for nom in ('terrain', 'rh', 'viewer'):
        if out[nom]['export_factures'][:3] == [200, True, True]:
            ecarts.append(f'{nom}:factures (écran {out[nom]["ecran_factures"]})')
    if out['c2_soi']['ecran_devis_c1'] in (403, 404) and out['c2_soi']['export_devis_c1'] == [200, True]:
        ecarts.append('c2_soi:devis_c1')
    out['ecarts'] = ecarts
    out['fuite_B'] = any(o['export_factures'][3] for o in out.values() if isinstance(o, dict) and 'export_factures' in o)
    return {'repro': bool(ecarts), 'observe': out}
