# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K46 — apporteurs PARQUÉS (D-ACRM-6 iii, réglage `CompanyProfile.apporteurs_actif` éteint par défaut) : le
portail public `GET crm/apporteur-portail/<token>/mes-deals/` (`apps/crm/public_views.py::public_apporteur_mes_deals`)
ne consulte pas `parcage.apporteurs_actifs` et sert encore les affaires (nom et ville du prospect, commissions).
Témoin : la route interne `GET crm/apporteurs/` (ApporteursParquesMixin) répond 404 réglage éteint."""
SONDE = {"constat": "C-APFS-066", "sha": "c9e72d5b20",
         "attendu": "repro si réglage éteint : témoin interne = 404 et portail public = 200 avec le deal (nom/ville) ; "
                    "allumé : interne 200",
         "modeles": ["crm.Apporteur", "crm.DealEnregistre", "crm.Lead", "parametres.CompanyProfile"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.crm.models import Lead, Apporteur, DealEnregistre
    from apps.crm.parcage import apporteurs_actifs
    from apps.parametres.models import CompanyProfile
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde APFS 066', slug='sonde-apfs-066')
    prof, _ = CompanyProfile.objects.get_or_create(company=co)
    prof.apporteurs_actif = False
    prof.save()
    perms = list(R['Administrateur'])
    role = Role.objects.create(company=co, nom='Administrateur', permissions=perms, est_systeme=True)
    adm = U.objects.create_user(username='apfs066-adm', password='x', company=co, role=role,
                                role_legacy=tier_for_role_fields('Administrateur', True, perms))
    ci = APIClient()
    ci.cookies['access_token'] = str(AccessToken.for_user(adm))
    ap = Apporteur.objects.create(company=co, nom='Apporteur 066', actif=True)
    lead = Lead.objects.create(company=co, nom='Prospect Secret 066', ville='Kenitra')
    DealEnregistre.objects.create(company=co, apporteur=ap, lead=lead, montant_commission_estime=Decimal('1500'))
    anon = APIClient()

    def get(c, url):
        r = c.get(url, **H)
        try:
            return r.status_code, r.json()
        except Exception:  # noqa
            return r.status_code, None

    obs = {'reglage_actif': apporteurs_actifs(co.id)}
    s_int, _ = get(ci, '/api/django/crm/apporteurs/')
    s_pub, corps = get(anon, f'/api/django/crm/apporteur-portail/{ap.token_acces}/mes-deals/')
    obs['eteint'] = {'interne_http': s_int, 'public_http': s_pub,
                     'public_deals': (corps or {}).get('deals') if isinstance(corps, dict) else None}
    prof.apporteurs_actif = True
    prof.save()
    s_int2, _ = get(ci, '/api/django/crm/apporteurs/')
    s_pub2, _ = get(anon, f'/api/django/crm/apporteur-portail/{ap.token_acces}/mes-deals/')
    obs['allume'] = {'reglage_actif': apporteurs_actifs(co.id), 'interne_http': s_int2, 'public_http': s_pub2}
    print(obs)
    deals = obs['eteint']['public_deals'] or []
    obs['repro'] = bool(not obs['reglage_actif'] and s_int == 404 and s_pub == 200
                        and any(d.get('client_nom') == 'Prospect Secret 066' for d in deals) and s_int2 == 200)
    return obs
