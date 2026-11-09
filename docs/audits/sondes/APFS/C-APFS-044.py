# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K09 — un compte interne SANS rôle fin (`role_id` nul) retombe sur le repli « historique » : `can_view_buy_prices`
/ `can_view_marge` / `can_view_client_pii` renvoient True quel que soit `role_legacy` (« normal » compris).
Comptes réels sans rôle : (a) provisionné comme `apps/identity/scim.py::ScimUsersView.post` (`create_user` sans rôle) ;
(b) Commercial dont le rôle est retiré par `apps/roles/services.py::remove_role_from_user` (retrait d'un groupe SCIM).
Témoin : le même Commercial AVEC son rôle ne voit ni `prix_achat` ni `marge_pct` sur `GET stock/produits/`."""
SONDE = {"constat": "C-APFS-044", "sha": "57d3fd371d",
         "attendu": "repro si le témoin (Commercial avec rôle) ne voit pas prix_achat, mais le compte SCIM sans rôle "
                    "et le Commercial après retrait du rôle voient prix_achat (500) sur stock/produits",
         "modeles": ["stock.Produit", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.roles.services import remove_role_from_user
    from apps.stock.models import Produit
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde APFS 044', slug='sonde-apfs-044')
    Produit.objects.create(company=co, nom='Onduleur sonde', sku='APFS-044', prix_vente=Decimal('900'),
                           prix_achat=Decimal('500'), quantite_stock=1)

    def client_jwt(u):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(u)))
        return c

    def lire(u):
        r = client_jwt(u).get('/api/django/stock/produits/', **H)
        try:
            data = r.json()
            rows = data.get('results', data) if isinstance(data, dict) else data
            row = next((x for x in rows if x.get('sku') == 'APFS-044'), {})
        except Exception:  # noqa
            row = {}
        return {'http': r.status_code, 'prix_achat_present': 'prix_achat' in row, 'prix_achat': row.get('prix_achat'),
                'marge_present': 'marge_pct' in row,
                'flags': {'buy': u.can_view_buy_prices, 'marge': u.can_view_marge, 'pii': u.can_view_client_pii},
                'role_id': u.role_id, 'role_legacy': u.role_legacy, 'menu_tier': u.menu_tier}

    perms = list(R['Commercial'])
    role, _ = Role.objects.get_or_create(company=co, nom='Commercial', defaults={'permissions': perms, 'est_systeme': True})
    com = U.objects.create_user(username='s044-commercial', password='x', company=co, role=role,
                                role_legacy=tier_for_role_fields('Commercial', True, perms))
    obs = {'commercial_a_prix_achat_voir': 'prix_achat_voir' in perms}
    obs['temoin_commercial_avec_role'] = lire(com)
    # (a) même appel que ScimUsersView.post
    scim = U.objects.create_user(username='s044-scim', email='scim@example.invalid', company=co,
                                 first_name='Prov', last_name='Scim', is_active=True)
    scim.set_unusable_password()
    scim.save(update_fields=['password'])
    obs['scim_sans_role'] = lire(scim)
    # (b) retrait du rôle (groupe SCIM retiré)
    obs['retrait_ok'] = remove_role_from_user(com, role.id)
    com = U.objects.get(pk=com.pk)
    obs['commercial_apres_retrait'] = lire(com)
    print(obs)
    t = obs['temoin_commercial_avec_role']
    temoin_ok = t['http'] == 200 and not t['prix_achat_present']
    defaut = obs['scim_sans_role']['prix_achat_present'] and obs['commercial_apres_retrait']['prix_achat_present']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
