# flake8: noqa  (sonde d'audit de parcours PF1 « Sécurité / multi-société », rejouable par scripts/sonde.py — METHODE §C.4)
"""K80 — garde de CLASSE : chaque route `list` d'un ViewSet routé des apps métier (stock, installations, sav, ventes,
crm, achats, facturation) est rejouée par la VRAIE route (APIClient + cookie JWT réel) en Admin RH et en Commercial
terrain (rôles système canoniques, périmètre posé comme `init_roles`), témoin Directeur. Une route qui répond 2xx
(ou 400 = garde de droit franchie, paramètre manquant) à un rôle qui ne porte AUCUN code du module de la vue
(`module_de_la_vue`) est un trou de lecture. Compte exact par app. Société vide (aucune donnée), transaction annulée."""
SONDE = {"constat": "C-APFS-080", "sha": "57d3fd371d",
         "attendu": "repro si au moins une route list répond 2xx/400 à Admin RH ou Commercial terrain sans code du "
                    "module de la vue ; attendu par le registre : 401/403 partout (comme crm/leads, ventes/factures)",
         "modeles": ["authentication.Company", "authentication.CustomUser", "roles.Role"]}


def sonde(ctx):
    import re
    from collections import defaultdict
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import get_resolver, URLResolver
    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import AccessToken
    from authentication.models import Company
    from authentication.role_tiers import tier_for_role_fields
    from authentication.permissions import module_de_la_vue
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    R = dict(reg.CANONICAL_SYSTEM_ROLES)
    PERIM = getattr(reg, 'SYSTEM_ROLE_PERIMETRES', {})
    PM = reg.PERMISSION_MODULE
    APPS = ('stock', 'installations', 'sav', 'ventes', 'crm', 'achats', 'facturation')
    co = Company.objects.create(nom='Sonde APFS 080 A', slug='sonde-apfs-080-a')

    def compte(nom, suffixe):
        perms = list(R[nom])
        role, _ = Role.objects.get_or_create(company=co, nom=nom, defaults={'permissions': perms, 'est_systeme': True})
        if PERIM.get(nom) and getattr(role, 'perimetre', None) != PERIM.get(nom):
            role.perimetre = PERIM[nom]
            role.save(update_fields=['perimetre'])
        return U.objects.create_user(username='apfs080-' + suffixe, password='x', company=co, role=role,
                                     role_legacy=tier_for_role_fields(nom, True, perms))

    comptes = {'Admin RH': compte('Admin RH', 'rh'), 'Commercial terrain': compte('Commercial terrain', 'ct'),
               'Directeur': compte('Directeur', 'dir')}
    clients = {}
    for k, u in comptes.items():
        c = APIClient()
        c.cookies['access_token'] = str(AccessToken.for_user(u))
        clients[k] = c

    routes = {}

    def walk(ps, pre=''):
        for p in ps:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, pre + str(p.pattern))
                continue
            cb = p.callback
            cls = getattr(cb, 'cls', None)
            actions = getattr(cb, 'actions', None) or {}
            if cls is None or actions.get('get') != 'list':
                continue
            parts = cls.__module__.split('.')
            if parts[0] != 'apps' or parts[1] not in APPS:
                continue
            route = pre + str(p.pattern)
            if not route.startswith('api/django/'):
                continue
            url = route.replace('^', '').replace('$', '')
            if '(?P' in url or '<' in url or '\\' in url:
                routes.setdefault(cls, ('PARAM', route))
                continue
            routes.setdefault(cls, ('OK', '/' + url.replace('\\.', '.')))

    walk(get_resolver().url_patterns)

    def appel(c, url):
        try:
            with transaction.atomic():
                r = c.get(url, **H)
                code = r.status_code
                transaction.set_rollback(True)
                return code
        except Exception as exc:  # noqa
            return 'EXC:' + type(exc).__name__

    def ouvert(code):
        return isinstance(code, int) and (200 <= code < 300 or code == 400)

    par_app = defaultdict(lambda: {'routes': 0, 'param': 0, 'rh_ouvert': 0, 'ct_ouvert': 0, 'les_deux': 0,
                                   'dir_ouvert': 0, 'rh_ferme': 0, 'ct_ferme': 0, 'autres': 0})
    ouverts = defaultdict(list)
    fermes = defaultdict(list)
    autres = []
    for cls, (etat, url) in sorted(routes.items(), key=lambda kv: kv[0].__module__ + kv[0].__name__):
        app = cls.__module__.split('.')[1]
        a = par_app[app]
        a['routes'] += 1
        if etat == 'PARAM':
            a['param'] += 1
            continue
        try:
            module = module_de_la_vue(cls())
        except Exception:  # noqa
            module = None
        codes = {k: sorted(c for c, m in PM.items() if m == module and c in set(R[k])) for k in comptes}
        res = {k: appel(clients[k], url) for k in comptes}
        nom = cls.__name__ + ' ' + url
        rh_o = ouvert(res['Admin RH']) and not codes['Admin RH']
        ct_o = ouvert(res['Commercial terrain']) and not codes['Commercial terrain']
        a['rh_ouvert'] += rh_o
        a['ct_ouvert'] += ct_o
        a['les_deux'] += rh_o and ct_o
        a['dir_ouvert'] += ouvert(res['Directeur'])
        a['rh_ferme'] += res['Admin RH'] in (401, 403)
        a['ct_ferme'] += res['Commercial terrain'] in (401, 403)
        if rh_o or ct_o:
            ouverts[app].append(re.sub(r'ViewSet$', '', cls.__name__) + ('' if res['Admin RH'] == 200 else ':%s' % res['Admin RH']))
        elif res['Admin RH'] in (401, 403) and res['Commercial terrain'] in (401, 403):
            fermes[app].append(re.sub(r'ViewSet$', '', cls.__name__))
        else:
            a['autres'] += 1
            autres.append(f"{cls.__name__} rh={res['Admin RH']} ct={res['Commercial terrain']} dir={res['Directeur']}")
    obs = {'ouverts': {k: ' '.join(v) for k, v in sorted(ouverts.items())},
           'par_app': {k: '%(routes)s routes, RH ouvert %(rh_ouvert)s, CT ouvert %(ct_ouvert)s, ferme %(rh_ferme)s, dir %(dir_ouvert)s' % v
                       for k, v in sorted(par_app.items())},
           'total_routes_list': sum(v['routes'] for v in par_app.values()),
           'total_rh_ouvert': sum(v['rh_ouvert'] for v in par_app.values()),
           'total_ct_ouvert': sum(v['ct_ouvert'] for v in par_app.values()),
           'fermes': {k: ' '.join(v) for k, v in fermes.items()}, 'autres': autres}
    pass  # sortie = dict renvoyé (6 000 car. max)
    obs['repro'] = bool(obs['total_rh_ouvert'] > 0 and obs['total_ct_ouvert'] > 0)
    return obs
