# flake8: noqa  (sonde de vérification C-L1-2, rejouable par scripts/sonde.py)
"""C-L1-2 — `marge_snapshot` servi à un compte au Role fin « Commercial » (COMMERCIAL_PERMISSIONS du registre,
sans `marge_voir`) : la garde du sérialiseur est `is_responsable` (vrai dès UNE permission d'écriture), pas
`can_view_marge`. Rejeu : le commercial crée son devis par POST atomic/, puis GET détail et GET liste.
Contre-épreuve : un Role fin identique + `marge_voir`. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-002", "sha": "1dfa7986c",
         "attendu": "Role Commercial sans marge_voir → marge_snapshot None (défaut : valeur servie)",
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
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes.domain.etudes import refresh_marge_snapshot
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 002', slug='sonde-advs-002')
    perms = [p for p in COMMERCIAL_PERMISSIONS if p != 'marge_voir']
    r_com = Role.objects.create(company=c, nom='Commercial sonde', permissions=perms)
    r_mar = Role.objects.create(company=c, nom='Commercial marge sonde', permissions=perms + ['marge_voir'])
    u = U.objects.create_user(username='sonde-advs-002', password='x', company=c, role=r_com)
    u2 = U.objects.create_user(username='sonde-advs-002-m', password='x', company=c, role=r_mar)
    cl = Client.objects.create(company=c, nom='Marge', prenom='Fuite', email='sonde-advs-002@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS002-P',
                                 prix_vente=Decimal('1000'), prix_achat=Decimal('600'), tva=Decimal('20'),
                                 quantite_stock=100)
    obs = {'commercial_has_marge_voir': 'marge_voir' in COMMERCIAL_PERMISSIONS,
           'is_responsable': u.is_responsable, 'can_view_marge': u.can_view_marge}

    def appel(api, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    api = APIClient()
    api.force_authenticate(u)
    s, cree = appel(api, 'post', '/api/django/ventes/devis/atomic/', {
        'client': cl.id, 'taux_tva': '20.00',
        'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': '10',
                    'prix_unitaire': '1000.00', 'taux_tva': '20'}]})
    obs['atomic'] = [s, cree.get('marge_snapshot', '<absente>') if isinstance(cree, dict) else None,
                     str(cree)[:200] if s >= 400 else '']
    dv = Devis.objects.filter(company=c).first()
    if dv is None:
        obs['erreur'] = 'aucun devis créé'
        return {'repro': False, 'observe': obs}
    refresh_marge_snapshot(dv)
    dv.refresh_from_db()
    obs['marge_snapshot_base'] = str(dv.marge_snapshot)
    s, det = appel(api, 'get', f'/api/django/ventes/devis/{dv.id}/')
    obs['detail_commercial'] = [s, det.get('marge_snapshot', '<absente>')]
    s, lst = appel(api, 'get', '/api/django/ventes/devis/')
    rows = lst.get('results', lst) if isinstance(lst, dict) else lst
    obs['liste_commercial'] = [s, [r.get('marge_snapshot', '<absente>') for r in rows][:3] if isinstance(rows, list) else str(rows)[:100]]
    api2 = APIClient()
    api2.force_authenticate(u2)
    s, det2 = appel(api2, 'get', f'/api/django/ventes/devis/{dv.id}/')
    obs['detail_avec_marge_voir'] = [s, det2.get('marge_snapshot', '<absente>')]
    fuite = obs['detail_commercial'][1] not in (None, '<absente>')
    return {'repro': bool(fuite and not obs['commercial_has_marge_voir']), 'observe': obs}
