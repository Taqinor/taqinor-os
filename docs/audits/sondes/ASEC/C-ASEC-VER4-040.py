SONDE = {"constat": "C-ASEC-VER4-040", "sha": "8fb8ba32b",
         "attendu": "REPRO = code décoratif : un rôle personnalisé SANS `stock_export` (stock_voir seul) obtient "
                    "200 sur POST /stock/produits/export-xlsx/ et /stock/mouvements/export-xlsx/, exactement comme "
                    "le rôle qui le porte (ASEC20 exempte encore stock_export, intervention_gerer, ventes_modifier "
                    "« la garde est posée par ASEC29/ASEC31/ASEC50 », aucune ne la pose)",
         "modeles": ["stock.Produit", "roles.Role", "authentication.CustomUser", "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal

    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from authentication.models import Company
    from apps.roles.models import Role
    from apps.stock.models import Produit

    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    a = Company.objects.create(nom='Sonde ASECV4040 A', slug='sonde-asecv4040-a')
    p = Produit.objects.create(company=a, nom='Panneau sonde 040', prix_vente=Decimal('100'))

    def compte(nom, perms):
        r = Role.objects.create(company=a, nom=nom, permissions=list(perms), est_systeme=False)
        u = User.objects.create_user(username=f'sonde-asecv4040-{nom}', password='x', company=a, role=r)
        api = APIClient()
        api.force_authenticate(u)
        return u, api

    u_sans, api_sans = compte('sans', ['stock_voir'])
    u_avec, api_avec = compte('avec', ['stock_voir', 'stock_export'])
    obs = {'porte_stock_export': {'sans': u_sans.has_erp_permission('stock_export'),
                                  'avec': u_avec.has_erp_permission('stock_export')}}
    for nom, api in (('sans_stock_export', api_sans), ('avec_stock_export', api_avec)):
        r1 = api.post('/api/django/stock/produits/export-xlsx/', {'ids': [p.pk]}, format='json', **H)
        r2 = api.post('/api/django/stock/mouvements/export-xlsx/', {}, format='json', **H)
        obs[nom] = {'produits_export_xlsx': [r1.status_code, r1.get('Content-Type', '')[:60]],
                    'mouvements_export_xlsx': [r2.status_code, r2.get('Content-Type', '')[:60]]}
    sans = obs['sans_stock_export']
    obs['repro'] = (sans['produits_export_xlsx'][0] == 200 and sans['mouvements_export_xlsx'][0] in (200, 202)
                    and not obs['porte_stock_export']['sans'])
    return obs
