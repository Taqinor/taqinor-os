# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K67 — `AchatsParametresViewSet.partial_update` n'exige que `stock_modifier` (porté par Technicien
responsable et Admin Ventes, rôles système) : séparation des tâches, retenue RAS-TVA, tolérances du
rapprochement 3 voies, blocages conformité/onboarding coupés. Société : sod_stricte=True, ras_tva_actif=True,
bloquer_paiement_conformite_expiree=True, onboarding_fournisseur_obligatoire=True, tolérance prix 2 %.
`PATCH stock/achats-parametres/<id>/` par chaque rôle. Témoin : Technicien (sans stock_modifier) = 403."""
SONDE = {"constat": "C-AAPV-107", "sha": "c6bd9b5d52",
         "attendu": "repro si Technicien responsable (et Admin Ventes) PATCH = 200 et les contrôles achats sont coupés ; Technicien 403",
         "modeles": ["stock.AchatsParametres", "roles.Role", "authentication.Company"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import AchatsParametres
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde AAPV 107', slug='sonde-aapv-107')

    def compte(nom):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='s107-' + nom.lower().replace(' ', '-'), password='x', company=co,
                                  role=role, role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.force_authenticate(u)
        return u, c

    def armer():
        p = AchatsParametres.for_company(co)
        p.sod_stricte = True
        p.ras_tva_actif = True
        p.bloquer_paiement_conformite_expiree = True
        p.onboarding_fournisseur_obligatoire = True
        p.tolerance_prix_pct = Decimal('2')
        p.save()
        return p

    corps = {'sod_stricte': False, 'ras_tva_actif': False, 'tolerance_prix_pct': '100',
             'bloquer_paiement_conformite_expiree': False, 'onboarding_fournisseur_obligatoire': False}
    obs = {}
    for nom in ['Technicien', 'Technicien responsable', 'Admin Ventes', 'Commercial']:
        u, c = compte(nom)
        p = armer()
        r = c.patch(f'/api/django/stock/achats-parametres/{p.pk}/', corps, format='json', **H)
        p.refresh_from_db()
        obs[nom] = {'stock_modifier': 'stock_modifier' in R[nom], 'parametres_modifier': 'parametres_modifier' in R[nom],
                    'http': r.status_code, 'sod_stricte': p.sod_stricte, 'ras_tva_actif': p.ras_tva_actif,
                    'tolerance_prix_pct': str(p.tolerance_prix_pct),
                    'onboarding_obligatoire': p.onboarding_fournisseur_obligatoire}
    print(obs)
    temoin_ok = obs['Technicien']['http'] == 403 and obs['Technicien']['sod_stricte'] is True
    tr = obs['Technicien responsable']
    defaut = tr['http'] == 200 and tr['sod_stricte'] is False and tr['ras_tva_actif'] is False \
        and tr['tolerance_prix_pct'].startswith('100')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
