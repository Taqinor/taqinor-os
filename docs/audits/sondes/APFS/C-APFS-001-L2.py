# flake8: noqa  (sonde d'audit PF1, seconde lentille — METHODE §B.5 ; rejouable par scripts/sonde.py)
"""C-APFS-001 L2 — autre angle que la sonde d'origine : au lieu de rejouer 9 portes choisies à la main, on
INVENTORIE toutes les routes DRF de /api/django/ et on demande à DRF lui-même (view.initial = authentification +
check_permissions, throttles neutralisés) si un compte PORTAIL client réel (provisionné par le vrai service dans la
société locale qui a le plus de prospects, mot de passe temporaire jamais changé) passe la garde, méthode par méthode.
Puis, pour chaque GET de LISTE (sans paramètre d'URL) qui passe, un vrai GET HTTP (cookie de la vraie connexion
/api/django/token/) : statut + nombre de lignes + noms de champs (aucune valeur imprimée).
Phase 3 : vrai appel HTTP sur tout le reste qui passe (détail avec un vrai id de la société, écritures à corps vide,
chaque appel annulé par point de sauvegarde) pour séparer « garde ouverte mais refus dans le corps de la vue » (403)
de « porte réellement ouverte » (2xx / 400 de validation / 404).
Sorties : résumé imprimé ; inventaire complet dans /tmp/pf1_l2_001.json du conteneur ; jeton d'accès du compte portail
(utilisateur annulé avec la transaction) dans /tmp/pf1_l2_token.txt pour le rejeu FastAPI de K60."""
SONDE = {"constat": "C-APFS-001", "sha": "496537c42",
         "attendu": "repro si des routes internes (hors /portail/, /auth/ personnelles, publiques AllowAny) laissent "
                    "passer le compte portail via un IsAuthenticated explicite, et que des GET de liste rendent 200 + "
                    "lignes de la société ; aucune route passée par IsAnyRole/ScopedPermission/défaut ASEC51",
         "modeles": ["authentication.CustomUser", "crm.Lead", "crm.Client", "portail.ComptePortailClient"]}


def sonde(ctx):
    import json, re, time
    from unittest import mock
    from django.core import mail
    from django.db import transaction
    from django.db.models import Count
    from django.urls import get_resolver
    from django.urls.resolvers import URLPattern, URLResolver, RoutePattern
    from rest_framework.exceptions import APIException, NotAuthenticated, PermissionDenied, AuthenticationFailed
    from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
    from authentication.models import Company
    from authentication.throttles import LoginRateThrottle
    from apps.crm.models import Client, Lead
    from apps.portail.services import provisionner_compte_portail_client
    H = {'HTTP_HOST': 'localhost'}
    mail.outbox = []
    out = {}

    # ── société locale la plus fournie (données réelles de la base de dev, annulées à la fin) ──
    top = Lead.objects.values('company').annotate(n=Count('id')).order_by('-n').first()
    if top:
        co = Company.objects.get(pk=top['company'])
    else:
        co = Company.objects.create(nom='Sonde APFS001 L2', slug='sonde-apfs001-l2')
    cl = Client.objects.filter(company=co).exclude(email='').exclude(email__isnull=True).first()
    if cl is None:
        cl = Client.objects.create(company=co, nom='ClientL2', prenom='APFS', email='apfs001l2@sonde.invalid')
    out['societe'] = {'id': co.id, 'leads': Lead.objects.filter(company=co).count(),
                      'clients': Client.objects.filter(company=co).count()}
    portail, cree = provisionner_compte_portail_client(co, cl.id)
    mdp = None
    for m in mail.outbox:
        t = re.search(r'(?i)mot de passe[^:\n]*:\s*(\S+)', m.body or '')
        if t:
            mdp = t.group(1).strip()
    out['provision'] = {'cree': cree, 'portee': portail.portee, 'must_change_password': portail.must_change_password,
                        'mdp_lu_dans_le_mail': bool(mdp)}
    if not mdp:
        mdp = 'Temp-APFS001-L2x9'
        portail.set_password(mdp)
        portail.save(update_fields=['password'])
    api = APIClient()
    with mock.patch.object(LoginRateThrottle, 'allow_request', return_value=True):
        r = api.post('/api/django/token/', {'username': portail.username, 'password': mdp}, format='json', **H)
    out['login'] = r.status_code
    jeton = api.cookies.get('access_token')
    if jeton is not None:
        with open('/tmp/pf1_l2_token.txt', 'w') as f:
            f.write(jeton.value)
        # Réplique LITTÉRALE de fastapi_ia/app/core/security.py::verify_token (PyJWT, HS256, exp requis,
        # token_type == access) avec la même clé (DJANGO_SECRET_KEY = SIGNING_KEY de SIMPLE_JWT).
        import jwt
        from django.conf import settings
        p = jwt.decode(jeton.value, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=['HS256'],
                       options={'require': ['exp'], 'verify_exp': True})
        out['K60_verify_token_replique'] = {'accepte': p.get('token_type') == 'access',
                                            'company_id': p.get('active_company_id') or p.get('company_id'),
                                            'role': p.get('role'), 'cle_portee': 'portee' in p}

    # ── inventaire des routes ──
    def walk(res, prefix=''):
        for p in res.url_patterns:
            pat = p.pattern
            s = str(pat) if isinstance(pat, RoutePattern) else pat.regex.pattern
            if isinstance(p, URLResolver):
                yield from walk(p, prefix + s)
            elif isinstance(p, URLPattern):
                yield prefix + s, p

    def concret(s):
        s = s.replace('^', '').replace('$', '').replace('\\Z', '')
        kw = []
        def rep_named(m):
            kw.append(m.group(1))
            return '1'
        # groupes nommés regex (contenu sans parenthèses imbriquées) et convertisseurs <int:pk>
        s = re.sub(r'\(\?P<(\w+)>[^()]*\)', rep_named, s)
        s = re.sub(r'<(?:\w+:)?(\w+)>', rep_named, s)
        s = s.replace('\\.', '.').replace('\\-', '-').replace('\\/', '/')
        ok = not re.search(r'[\[\]()*+?|\\]', s)
        return '/' + s.lstrip('/'), kw, ok

    factory = APIRequestFactory()
    lignes = []
    vus = set()
    for brut, p in walk(get_resolver()):
        cb = p.callback
        cls = getattr(cb, 'cls', None)
        if cls is None or 'format' in brut:
            continue
        chemin, kw, ok = concret(brut)
        if not chemin.startswith('/api/django/'):
            continue
        actions = getattr(cb, 'actions', None)
        if actions:
            methodes = list(actions.keys())
        else:
            methodes = [m for m in ('get', 'post', 'put', 'patch', 'delete') if hasattr(cls, m)]
        for meth in methodes:
            cle = (chemin, meth)
            if cle in vus:
                continue
            vus.add(cle)
            kwargs = {k: '1' for k in kw}
            req = getattr(factory, meth)(chemin, **H) if meth in ('get', 'delete') else \
                getattr(factory, meth)(chemin, {}, format='json', **H)
            force_authenticate(req, user=portail)
            ligne = {'route': chemin, 'm': meth.upper(), 'vue': f'{cls.__module__}::{cls.__name__}',
                     'action': (actions or {}).get(meth), 'kw': bool(kw), 'chemin_ok': ok}
            try:
                view = cls(**(getattr(cb, 'initkwargs', None) or {}))
                if actions:
                    view.action_map = actions
                    for mm, a in actions.items():
                        if hasattr(view, a):
                            setattr(view, mm, getattr(view, a))
                view.headers = {}
                view.args, view.kwargs = (), kwargs
                drf = view.initialize_request(req, **kwargs)
                view.request = drf
                view.format_kwarg = None
                try:
                    ligne['perms'] = [type(x).__name__ for x in view.get_permissions()]
                except Exception as e:
                    ligne['perms'] = ['?' + type(e).__name__]
                view.check_throttles = lambda r: None
                with transaction.atomic():
                    view.initial(drf)
                ligne['passe'] = True
                if kw and hasattr(view, 'get_queryset'):
                    try:  # un VRAI id de la société (queryset tel que la vue le borne pour ce compte)
                        with transaction.atomic():
                            pk = view.get_queryset().values_list('pk', flat=True).first()
                        if pk is not None:
                            ligne['pk'] = pk
                    except Exception:
                        pass
            except (PermissionDenied, NotAuthenticated, AuthenticationFailed) as e:
                ligne['passe'] = False
                ligne['refus'] = type(e).__name__ + ':' + str(getattr(e, 'get_codes', lambda: '')())[:40]
            except Exception as e:
                ligne['passe'] = None
                ligne['erreur'] = type(e).__name__ + ':' + str(e)[:80]
            lignes.append(ligne)

    # ── vrais GET de liste sur ce qui passe (hors /portail/ et /auth/) ──
    debut = time.time()
    for l in lignes:
        if not (l.get('passe') and l['m'] == 'GET' and not l['kw'] and l['chemin_ok']):
            continue
        if time.time() - debut > 480:
            l['http'] = 'budget'
            continue
        try:
            with transaction.atomic():
                rr = api.get(l['route'], **H)
            l['http'] = rr.status_code
            if rr.status_code == 200 and 'json' in (rr.get('Content-Type') or ''):
                body = rr.json()
                rows = body.get('results', body.get('rows')) if isinstance(body, dict) else body
                if isinstance(rows, list):
                    l['n'] = body.get('count', len(rows)) if isinstance(body, dict) else len(rows)
                    l['champs'] = sorted(rows[0].keys())[:25] if rows and isinstance(rows[0], dict) else []
                elif isinstance(body, dict):
                    l['cles'] = sorted(body.keys())[:25]
        except Exception as e:
            l['http'] = 'exc:' + type(e).__name__

    # ── phase 3 : vrai appel HTTP sur le reste des routes `IsAuthenticated` qui passent la garde (détail avec un vrai id quand la vue en a
    #    un, écritures à corps vide) — hors /auth/, /token/, /users/ (déconnexion, mot de passe, bascule) ; chaque
    #    appel dans un point de sauvegarde, tout est annulé avec la transaction de la sonde ──
    debut = time.time()
    for l in lignes:
        if not l.get('passe') or 'http' in l or not l['chemin_ok'] or 'IsAuthenticated' not in (l.get('perms') or []):
            continue
        if any(x in l['route'] for x in ('/auth/', '/token/', '/users/')):
            continue
        if time.time() - debut > 300:
            l['http'] = 'budget'
            continue
        route = l['route']
        if l.get('pk') is not None:
            route = re.sub(r'/1/', '/%s/' % l['pk'], route, count=1)
        try:
            with transaction.atomic():
                f = getattr(api, l['m'].lower())
                rr = f(route, **H) if l['m'] in ('GET', 'DELETE') else f(route, {}, format='json', **H)
                l['http'] = rr.status_code
                if rr.status_code < 300 and 'json' in (rr.get('Content-Type') or ''):
                    body = rr.json()
                    l['cles'] = sorted(body.keys())[:25] if isinstance(body, dict) else ('liste', len(body))
                elif rr.status_code < 300:
                    l['cles'] = rr.get('Content-Type')
                raise RuntimeError('annuler ce point de sauvegarde')
        except RuntimeError:
            if 'http' not in l:
                l['http'] = 'exc:RuntimeError'
        except Exception as e:
            l['http'] = 'exc:' + type(e).__name__

    passent = [l for l in lignes if l.get('passe')]
    with open('/tmp/pf1_l2_001.json', 'w') as f:
        json.dump({'meta': out, 'lignes': lignes}, f, ensure_ascii=True, default=str)
    vues_isauth = sorted({l['vue'] for l in passent if 'IsAuthenticated' in (l.get('perms') or [])})
    out['inventaire'] = {'routes_methodes': len(lignes), 'passent': len(passent),
                         'passent_hors_portail_auth': len([l for l in passent if '/portail/' not in l['route']
                                                           and '/auth/' not in l['route']]),
                         'erreurs_eval': len([l for l in lignes if l.get('passe') is None]),
                         'vues_passees_avec_IsAuthenticated': len(vues_isauth),
                         'get_liste_200_avec_lignes': len([l for l in passent if l.get('http') == 200 and l.get('n')]),
                         'http_par_statut': dict(sorted(__import__('collections').Counter(
                             str(l.get('http', 'non_appele')) for l in passent).items()))}
    temoin = [l for l in lignes if l['route'] == '/api/django/crm/leads/' and l['m'] == 'GET']
    out['temoin_crm_leads'] = temoin[0].get('passe') if temoin else 'absent'
    portail.refresh_from_db()
    out['must_change_password_toujours'] = portail.must_change_password
    out['repro'] = bool(out['login'] == 200 and vues_isauth and out['temoin_crm_leads'] is False)
    print(out)
    return out
