# flake8: noqa  (sonde de contre-visite VER1, rejouable par scripts/sonde.py)
"""VER1-202 (AARG52) : inventaire COMPLET des vues gardées par `IsResponsableOrAdmin` — classe ET `@action(permission_classes=…)`
(le test `test_vues_sans_module_figees` ne lit que `cls.permission_classes`) — dont le module ne se résout pas (`module_de_la_vue`
= None) : aucune app hors `APPS_SANS_MODULE` (+ portail, fermé voulu) ne doit y figurer sans que l'écriture d'un rôle fin soit
refusée ; et effet réel d'écriture d'un rôle « RH seul » sur chaque vue non résolue hors fondation. Lecture seule."""
SONDE = {"constat": "C-AARG-007", "sha": "06ced8b1a",
         "attendu": "toute vue IsResponsableOrAdmin sans module hors fondation refuse l'écriture d'un rôle fin non admin",
         "modeles": ["authentication.Company"]}


def sonde(ctx):
    from types import SimpleNamespace
    from django.urls import get_resolver
    from rest_framework.permissions import SAFE_METHODS
    from authentication.permissions import APPS_SANS_MODULE, IsResponsableOrAdmin, module_de_la_vue

    def iter_cb(motifs):
        for m in motifs:
            if hasattr(m, 'url_patterns'):
                yield from iter_cb(m.url_patterns)
            else:
                cb = getattr(m, 'callback', None)
                if cb is not None:
                    yield cb

    non_resolues = {}
    n_vues = 0
    for cb in iter_cb(get_resolver().url_patterns):
        cls = getattr(cb, 'cls', None)
        if cls is None:
            continue
        niveaux = [('classe', list(getattr(cls, 'permission_classes', []) or []))]
        actions = getattr(cb, 'actions', None) or {}
        for methode, nom in actions.items():
            fn = getattr(cls, nom, None)
            kw = getattr(fn, 'kwargs', None) or {}
            if 'permission_classes' in kw:
                niveaux.append((f'action:{nom}', list(kw['permission_classes'])))
        for niveau, perms in niveaux:
            if not any(p is IsResponsableOrAdmin for p in perms):
                continue
            n_vues += 1
            vue = cls.__new__(cls)
            if module_de_la_vue(vue) is not None:
                continue
            parties = cls.__module__.split('.')
            app = parties[1] if parties[0] == 'apps' and len(parties) > 1 else parties[0]
            non_resolues.setdefault(app, set()).add(f'{cls.__module__}.{cls.__name__}[{niveau}]')
    hors_fondation = {a: sorted(v)[:4] for a, v in non_resolues.items() if a not in APPS_SANS_MODULE}
    fondation = sorted(a for a in non_resolues if a in APPS_SANS_MODULE)
    obs = {'vues_IsResponsableOrAdmin_inspectees': n_vues, 'apps_non_resolues_fondation_toleree': fondation,
           'apps_non_resolues_HORS_fondation(refusees en ecriture)': hors_fondation}
    print(obs)
    # repro = écart : une app non résolue hors fondation autre que portail (non planifiée) ou une garde qui laisserait passer l'écriture
    class _U:  # rôle fin non administrateur
        is_authenticated = True
        is_responsable = True
        is_superuser = False
        is_admin_role = False
        role_id = 1
    sans_garde = []
    for app in hors_fondation:
        vue = type('V', (), {'__module__': f'apps.{app}.views'})()
        req = SimpleNamespace(user=_U(), method='POST')
        if IsResponsableOrAdmin().has_permission(req, vue):
            sans_garde.append(app)
    return {'repro': bool(sans_garde), 'sans_garde': sans_garde, **obs}
