# flake8: noqa  (sonde de vérification C8-1, rejouable par scripts/sonde.py)
"""C8-1 — les rôles fins SANS aucun code ventes (Admin RH, Technicien, Commercial terrain — listes du registre
`apps/roles/permissions_registre.py`) lisent-ils liste / fiche / historique / prefill-site / `/proposal` d'un devis
envoyé créé par un admin ? Garde lue : `DevisViewSet.get_permissions` → `IsAnyRole` (aucun module), `/proposal` →
`IsInternalWriterOrPortalClientOwner` (`is_responsable`). La portée d'enregistrement (`visible_user_ids`) peut
réduire le constat : on la mesure par rôle. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-041", "sha": "1dfa7986c",
         "attendu": "rôle sans code ventes → 403 sur liste/fiche/historique/prefill-site/proposal (défaut : 200)",
         "modeles": ["ventes.Devis", "roles.Role"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as R
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 041', slug='sonde-advs-041')
    adm = U.objects.create_user(username='sonde-advs-041-adm', password='x', role_legacy='admin', company=c)
    roles = {'Admin RH': R.ADMIN_RH_PERMISSIONS, 'Technicien': R.TECHNICIEN_PERMISSIONS,
             'Commercial terrain': R.COMMERCIAL_TERRAIN_PERMISSIONS, 'Viewer (témoin ventes_voir)': R.VIEWER_PERMISSIONS}
    users = {}
    for i, (nom, perms) in enumerate(roles.items()):
        r = Role.objects.create(company=c, nom=f'{nom} sonde', permissions=list(perms))
        users[nom] = U.objects.create_user(username=f'sonde-advs-041-{i}', password='x', company=c, role=r)
    cl = Client.objects.create(company=c, nom='Lecture', prenom='Fuite', email='sonde-advs-041@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS041-P',
                                 prix_vente=Decimal('1000'), prix_achat=Decimal('600'), tva=Decimal('20'),
                                 quantite_stock=100)
    ond = Produit.objects.create(company=c, nom='Onduleur réseau Huawei 10kW Monophasé', sku='ADVS041-O',
                                 prix_vente=Decimal('14000'), prix_achat=Decimal('9000'), tva=Decimal('20'),
                                 quantite_stock=100)

    def appel(api, meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth == 'get':
                    r = api.get(url, corps or {}, HTTP_HOST='localhost')
                else:
                    r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
            txt = brut.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt), brut
            except Exception:
                return r.status_code, {'_brut': txt[:120]}, brut
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}, b''

    a = APIClient()
    a.force_authenticate(adm)
    s, cree, _ = appel(a, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': '10',
                    'prix_unitaire': '1000.00', 'taux_tva': '20'},
                   {'produit': ond.id, 'designation': 'Onduleur réseau Huawei 10kW Monophasé', 'quantite': '1',
                    'prix_unitaire': '14000.00', 'taux_tva': '20'}]})
    obs = {'atomic_admin': s}
    dv = Devis.objects.filter(company=c).first()
    if dv is None:
        obs['erreur'] = str(cree)[:300]
        return {'repro': False, 'observe': obs}
    Devis.objects.filter(pk=dv.pk).update(statut='envoye')
    obs['reference'] = dv.reference
    s, corps, pdf = appel(a, 'get', f'/api/django/ventes/devis/{dv.id}/proposal/')
    obs['admin_proposal'] = [s, pdf[:4].decode('latin-1') if s == 200 else str(corps)[:200]]
    fuites = {}
    for nom, u in users.items():
        api = APIClient()
        api.force_authenticate(u)
        res = {'is_responsable': u.is_responsable}
        s, lst, _ = appel(api, 'get', '/api/django/ventes/devis/')
        rows = lst.get('results', lst) if isinstance(lst, dict) else lst
        refs = [r.get('reference') for r in rows] if isinstance(rows, list) else []
        res['liste'] = [s, dv.reference in refs]
        s, det, _ = appel(api, 'get', f'/api/django/ventes/devis/{dv.id}/')
        res['fiche'] = [s, det.get('total_ttc') if isinstance(det, dict) else None]
        s, _, _ = appel(api, 'get', f'/api/django/ventes/devis/{dv.id}/historique/')
        res['historique'] = s
        s, pf, _ = appel(api, 'get', '/api/django/ventes/devis/prefill-site/', {'client': cl.id})
        res['prefill_site'] = s
        s, pcorps, pdf = appel(api, 'get', f'/api/django/ventes/devis/{dv.id}/proposal/')
        res['proposal'] = [s, pdf[:4].decode('latin-1') if s == 200 else str(pcorps)[:160]]
        obs[nom] = res
        lus = [k for k in ('fiche', 'proposal') if res[k][0] == 200] + (['liste'] if res['liste'][1] else [])
        if 'témoin' not in nom and lus:
            fuites[nom] = lus
    obs['fuites'] = fuites
    return {'repro': bool(fuites), 'observe': obs}
