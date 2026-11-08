# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K43 — liste blanche d'IP par société (NTSEC11) : `apps/identity/middleware.py::_is_public_path` teste des
SOUS-CHAÎNES (« /proposal », « /webhook », « /public/ »…) : des routes INTERNES authentifiées qui les contiennent
échappent au mode ENFORCE. Société A en `NetworkPolicy(mode=enforce, applies_to=all)` avec une seule plage
10.99.0.0/24, requêtes depuis 203.0.113.7 (hors plage), jeton JWT réel en cookie.
Témoin : `GET crm/leads/` → 403 « Adresse IP non autorisée »."""
SONDE = {"constat": "C-APFS-065", "sha": "c9e72d5b20",
         "attendu": "repro si le témoin crm/leads/ = 403 IP et que ventes/devis/<id>/proposal/ ou publicapi/webhooks/ "
                    "répondent autre chose que le 403 IP",
         "modeles": ["identity.NetworkPolicy", "identity.IpAllowRule", "ventes.Devis", "authentication.Company"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.identity.models import NetworkPolicy, IpAllowRule
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    H = {'HTTP_HOST': 'localhost', 'REMOTE_ADDR': '203.0.113.7'}
    U = get_user_model()
    R = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='Sonde APFS 065', slug='sonde-apfs-065')
    pol = NetworkPolicy.objects.create(company=co, mode=NetworkPolicy.Mode.ENFORCE,
                                       applies_to=NetworkPolicy.AppliesTo.ALL)
    IpAllowRule.objects.create(company=co, policy=pol, cidr='10.99.0.0/24', label='bureau')

    def compte(nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom,
                                             defaults={'permissions': perms, 'est_systeme': True})
        u = U.objects.create_user(username='apfs065-' + suffixe, password='x', company=co, role=role,
                                  role_legacy=tier_for_role_fields(nom, True, perms))
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        return c

    adm = compte('Administrateur', 'adm')
    com = compte('Commercial', 'com')
    cl = Client.objects.create(company=co, nom='Client', prenom='065', email='c065@example.invalid')
    dv = Devis.objects.create(company=co, reference='DEV-APFS-065', client=cl, statut=Devis.Statut.BROUILLON)

    def appel(c, methode, url, **kw):
        try:
            r = getattr(c, methode)(url, format='json', **H, **kw) if methode != 'get' else c.get(url, **H)
        except Exception as exc:  # noqa — une exception de la VUE prouve déjà que le middleware a laissé passer
            return {'http': 'exception vue', 'bloque_ip': False, 'detail': repr(exc)[:120]}
        corps = ''
        try:
            corps = str(r.json())[:140]
        except Exception:  # noqa
            corps = (r.get('Content-Type') or '')
        return {'http': r.status_code, 'bloque_ip': 'Adresse IP non autoris' in corps, 'detail': corps[:140]}

    obs = {
        'temoin_leads_commercial': appel(com, 'get', '/api/django/crm/leads/'),
        'temoin_leads_admin': appel(adm, 'get', '/api/django/crm/leads/'),
        'proposal_devis_reel_commercial': appel(com, 'get', f'/api/django/ventes/devis/{dv.id}/proposal/'),
        'proposal_devis_reel_admin': appel(adm, 'get', f'/api/django/ventes/devis/{dv.id}/proposal/'),
        'publicapi_webhooks_liste_admin': appel(adm, 'get', '/api/django/publicapi/webhooks/'),
    }
    print(obs)
    temoin = obs['temoin_leads_commercial']['bloque_ip'] and obs['temoin_leads_admin']['bloque_ip']
    passes = [k for k in obs if not k.startswith('temoin') and not obs[k]['bloque_ip']]
    obs['routes_passant_le_filtre_ip'] = passes
    obs['repro'] = bool(temoin and passes)
    return obs
