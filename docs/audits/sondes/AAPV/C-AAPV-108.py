# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K68 — `MouvementRebutViewSet.get_permissions` : `create` → `IsAnyRole`. Un Commercial et un Viewer (rôles
système, sans `stock_mouvement`) déclarent un rebut de 30 par `POST stock/mouvements-rebut/` : MouvementStock
REBUT posé, `quantite_stock` −30. La réponse (et la liste, IsAnyRole) sert `valeur_perte` = coût d'achat × qté
à des rôles sans `prix_achat_voir` (D-ASTK-2). Témoin : `POST stock/mouvements/` (même sortie de stock, garde
`stock_mouvement`) refuse le même Commercial (403) ; le Technicien (qui porte `stock_mouvement`) est hors défaut."""
SONDE = {"constat": "C-AAPV-108", "sha": "c6bd9b5d52",
         "attendu": "repro si témoin mouvements/ 403 ET mouvements-rebut/ 201 pour Commercial/Viewer avec stock −30 et valeur_perte servie",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.MouvementRebut", "roles.Role",
                     "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import Produit, MouvementStock
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 108', slug='sonde-aapv-108')

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s108-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    obs = {}
    for nom in ['Commercial', 'Viewer']:
        u, c = compte(nom)
        p = Produit.objects.create(company=co, nom=f'Onduleur S108 {nom}', sku=f'AAPV-108-{nom[:3]}',
                                   prix_vente=Decimal('8000'), prix_achat=Decimal('5000'), quantite_stock=100)
        t = c.post('/api/django/stock/mouvements/', {'produit': p.id, 'type_mouvement': 'sortie', 'quantite': 30,
                                                    'note': 'témoin'}, format='json', **H)
        p.refresh_from_db()
        stock_apres_temoin = p.quantite_stock
        r = c.post('/api/django/stock/mouvements-rebut/', {'produit': p.id, 'quantite': 30, 'motif': 'casse',
                                                          'note': 'cassé'}, format='json', **H)
        p.refresh_from_db()
        lst = c.get('/api/django/stock/mouvements-rebut/', **H)
        rows = lst.data.get('results', lst.data) if lst.status_code == 200 and isinstance(lst.data, dict) else (
            lst.data if lst.status_code == 200 else [])
        obs[nom] = {'stock_mouvement': 'stock_mouvement' in R[nom], 'prix_achat_voir': 'prix_achat_voir' in R[nom],
                    'temoin_mouvements_http': t.status_code, 'stock_apres_temoin': stock_apres_temoin,
                    'rebut_http': r.status_code,
                    'rebut_valeur_perte': (r.data.get('valeur_perte') if r.status_code < 400 else str(r.data)[:100]),
                    'stock_final': p.quantite_stock,
                    'mvt_rebut': MouvementStock.objects.filter(company=co, produit=p).exclude(
                        note='témoin').values_list('type_mouvement', 'quantite').first(),
                    'liste_http': lst.status_code,
                    'liste_valeur_perte': [row.get('valeur_perte') for row in rows][:2]}
    print(obs)
    temoin_ok = all(obs[n]['temoin_mouvements_http'] == 403 and obs[n]['stock_apres_temoin'] == 100
                    for n in obs)
    defaut = all(obs[n]['rebut_http'] == 201 and obs[n]['stock_final'] == 70 for n in obs)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
