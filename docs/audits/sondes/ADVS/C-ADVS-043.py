# flake8: noqa  (sonde de vérification C8-2 — extension de C-ADVS-002, rejouable par scripts/sonde.py)
"""C8-2 — extension de C-ADVS-002 (Commercial déjà prouvé) aux rôles fins Admin RH, Technicien et Commercial
terrain : `DevisSerializer.get_marge_snapshot` sert la marge à tout `is_responsable` (vrai dès UNE écriture), sans
`marge_voir`. Devis créé par un admin (POST atomic/) ; pour le Technicien (portée équipe), un second devis lui est
attribué (`created_by`) par ORM pour franchir sa portée d'enregistrement — seule la garde du sérialiseur est
mesurée. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-043", "sha": "1dfa7986c",
         "attendu": "rôle sans marge_voir → marge_snapshot None (défaut : valeur servie)",
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
    from apps.ventes.domain.etudes import refresh_marge_snapshot
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 043', slug='sonde-advs-043')
    adm = U.objects.create_user(username='sonde-advs-043-adm', password='x', role_legacy='admin', company=c)
    roles = {'Admin RH': R.ADMIN_RH_PERMISSIONS, 'Technicien': R.TECHNICIEN_PERMISSIONS,
             'Commercial terrain': R.COMMERCIAL_TERRAIN_PERMISSIONS}
    users = {}
    for i, (nom, perms) in enumerate(roles.items()):
        r = Role.objects.create(company=c, nom=f'{nom} sonde 043', permissions=list(perms))
        users[nom] = U.objects.create_user(username=f'sonde-advs-043-{i}', password='x', company=c, role=r)
    cl = Client.objects.create(company=c, nom='Marge', prenom='Roles', email='sonde-advs-043@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS043-P',
                                 prix_vente=Decimal('1000'), prix_achat=Decimal('600'), tva=Decimal('20'),
                                 quantite_stock=100)

    def appel(api, meth, url, corps=None):
        try:
            with transaction.atomic():
                rr = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = rr.content.decode('utf-8', 'replace')
            try:
                return rr.status_code, json.loads(txt)
            except Exception:
                return rr.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    a = APIClient()
    a.force_authenticate(adm)
    corps = {'client': cl.id, 'taux_tva': '20.00',
             'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': '10',
                         'prix_unitaire': '1000.00', 'taux_tva': '20'}]}
    appel(a, 'post', '/api/django/ventes/devis/atomic/', corps)
    appel(a, 'post', '/api/django/ventes/devis/atomic/', corps)
    d1, d2 = list(Devis.objects.filter(company=c).order_by('id'))[:2]
    Devis.objects.filter(pk=d2.pk).update(created_by=users['Technicien'])
    for d in (d1, d2):
        refresh_marge_snapshot(d)
    d1.refresh_from_db()
    obs = {'marge_base': str(d1.marge_snapshot)}
    fuites = {}
    for nom, u in users.items():
        api = APIClient()
        api.force_authenticate(u)
        cible = d2 if nom == 'Technicien' else d1
        s, det = appel(api, 'get', f'/api/django/ventes/devis/{cible.id}/')
        val = det.get('marge_snapshot', '<absente>') if isinstance(det, dict) else None
        obs[nom] = {'marge_voir': 'marge_voir' in roles[nom], 'can_view_marge': u.can_view_marge,
                    'is_responsable': u.is_responsable, 'fiche': [s, val]}
        if s == 200 and val not in (None, '<absente>'):
            fuites[nom] = val
    obs['fuites'] = fuites
    return {'repro': bool(fuites), 'observe': obs}
