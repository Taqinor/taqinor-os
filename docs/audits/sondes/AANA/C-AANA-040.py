"""Sonde AANA50 (acceptation en direct du groupe AANA), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
Rejoue C-AANA-040 (audit analyse du 05/10, §6) : l'EDI X12 de l'API publique (zéro appelant de production) était servi.
"""
SONDE = {
    'constat': 'C-AANA-040',
    'sha': '5908d43bb',
    'attendu': "défaut absent : aucune route edi n'est servie (404), apps.publicapi.edi / edi_partners non importables, PartenaireEdi hors état Django",
}


def sonde(ctx):
    import importlib.util
    from django.apps import apps
    from django.urls import Resolver404, resolve
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.publicapi.models import ApiKey
    from apps.publicapi.portees import ALL_SCOPES
    co = Company.objects.create(nom='Sonde 040', slug='sonde-aana-040')
    _c, brute = ApiKey.issue(company=co, label='edi', scopes=list(ALL_SCOPES))
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION='Api-Key %s' % brute)
    chemins = ['/api/public/v1/edi/', '/api/public/v1/edi/810/', '/api/public/v1/edi/850/', '/api/django/publicapi/edi/']
    statuts, routes_edi = {}, []
    for ch in chemins:
        statuts[ch] = api.get(ch, HTTP_HOST='localhost').status_code
        try:
            r = resolve(ch)
            cible = '%s.%s %s' % (r.func.__module__, getattr(r.func, '__name__', ''), r.url_name or '')
            if 'edi' in cible.lower():
                routes_edi.append((ch, cible))
        except Resolver404:
            pass
    importables = [n for n in ('apps.publicapi.edi', 'apps.publicapi.edi_partners') if importlib.util.find_spec(n)]
    try:
        apps.get_model('publicapi', 'PartenaireEdi')
        modele = True
    except LookupError:
        modele = False
    ok = all(s == 404 for s in statuts.values()) and not routes_edi and not importables and not modele
    print('statuts=%s routes_edi=%s modules_importables=%s modele_dans_etat=%s' % (statuts, routes_edi, importables, modele))
    return {'repro': ok, 'statuts': statuts, 'routes_edi': routes_edi, 'modules': importables, 'modele': modele}
