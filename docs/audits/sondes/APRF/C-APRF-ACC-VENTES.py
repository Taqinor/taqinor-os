SONDE = {"constat": "C-APRF-ACC-VENTES", "sha": "665a4ce53",
         "attendu": "APRF42 (C-APRF-001…005, 028 export devis) : liste des devis (page_size 5 / 25 / 50), « Relances du "
                    "jour » (action-requise), export devis et /proposal, mesurés à DEUX tailles de données (société "
                    "anonymisée 4, puis +20 devis clonés avec leurs lignes dans la transaction annulée) : nombre de "
                    "requêtes SQL identique (pente 0 ± 1), 0 réponse 503, totaux de liste = Devis.total_ttc relu sans "
                    "préchargement, electrical_design absent de la liste, /proposal même nombre de pages et mêmes montants "
                    "avant / après.",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink"]}

# ---- outillage commun APRF (copié dans chaque sonde APRF-ACC : une sonde est autonome) ----
H = {'HTTP_HOST': 'localhost'}


def _api(user):
    from rest_framework.test import APIClient
    api = APIClient()
    api.force_authenticate(user)
    return api


def _mesure(api, url, methode='get', data=None):
    """(statut, nb requêtes SQL, octets, corps JSON|None) d'un appel HTTP réel (DRF APIClient)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as ctx:
        if methode == 'get':
            r = api.get(url, data or {}, **H)
        else:
            r = api.post(url, data or {}, format='json', **H)
    corps = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
    js = None
    if 'json' in (r.get('Content-Type') or ''):
        import json
        try:
            js = json.loads(corps)
        except ValueError:
            js = None
    return r.status_code, len(ctx.captured_queries), len(corps), js


def _lignes(js):
    if isinstance(js, dict):
        return js.get('results', js.get('data', []))
    return js or []


def _cloner(obj, i, uniques=(), enfants=()):
    """Clone `obj` (pk neuf, champs uniques suffixés) et ses enfants par relation inverse."""
    import copy
    o = copy.copy(obj)
    o.pk = None
    o.id = None
    o._state.adding = True
    for f in uniques:
        v = getattr(obj, f)
        setattr(o, f, ('%s-K%d' % (v, i))[:40] if v else v)
    o.save()
    for rel, fk in enfants:
        for e in getattr(obj, rel).all():
            e2 = copy.copy(e)
            e2.pk = None
            e2.id = None
            e2._state.adding = True
            setattr(e2, fk, o)
            e2.save()
    return o


def _plat(a, b, tol=1):
    return abs(b - a) <= tol
# ---- fin outillage commun ----


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from apps.ventes.models import Devis
    U = get_user_model()
    co = 4
    u = U.objects.filter(company_id=co, is_active=True).order_by('id').first()
    api = _api(u)
    out, ok = {}, {}
    url = '/api/django/ventes/devis/'

    def liste():
        res = {}
        for ps in (5, 25, 50):
            st, nq, nb, js = _mesure(api, url, data={'page_size': ps})
            rows = _lignes(js)
            res[ps] = {'st': st, 'q': nq, 'o': nb, 'n': len(rows),
                       'ttc': {r['id']: r.get('total_ttc') for r in rows[:5]},
                       'ed': any('electrical_design' in r and r['electrical_design'] for r in rows)}
        return res

    def autres():
        st, nq, nb, js = _mesure(api, url + 'action-requise/')
        cpt = {k: v.get('count') for k, v in ((js or {}).get('buckets') or {}).items()}
        ar = {'st': st, 'q': nq, 'o': nb, 'cpt': cpt}
        ids = list(Devis.objects.filter(company_id=co).order_by('-id').values_list('id', flat=True)[:30])
        st2, nq2, nb2, _ = _mesure(api, '/api/django/imports/export/devis/', 'post', {'ids': ids})
        return ar, {'st': st2, 'q': nq2, 'o': nb2, 'n_ids': len(ids)}

    def proposal(did):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as c:
            r = api.get('%s%s/proposal/' % (url, did), **H)
        corps = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        if r.status_code != 200:
            return {'st': r.status_code}
        import fitz
        import re
        doc = fitz.open(stream=corps, filetype='pdf')
        txt = '\n'.join(p.get_text() for p in doc)
        montants = sorted(set(re.findall(r'\d{1,3}(?:[  \xa0]\d{3})+,\d{2}', txt)))[:12]
        return {'st': 200, 'pages': doc.page_count, 'q': len(c.captured_queries), 'montants': montants}

    avant = liste()
    ar1, ex1 = autres()
    d_demo = Devis.objects.filter(company_id=co, lignes__isnull=False).order_by('-id').first()
    pr1 = proposal(d_demo.id)
    # Taille 2 : +20 devis clonés (avec leurs lignes) dans la transaction annulée.
    src = list(Devis.objects.filter(company_id=co, lignes__isnull=False).distinct().order_by('-id')[:20])
    clones = [_cloner(d, i, uniques=('reference',), enfants=(('lignes', 'devis'),)) for i, d in enumerate(src)]
    # Les clones entrent dans deux paniers de « Relances du jour » (update() : aucun signal de transition).
    import datetime
    from django.utils import timezone
    Devis.objects.filter(pk__in=[c.pk for c in clones[0::2]]).update(statut='refuse', motif_refus='')
    Devis.objects.filter(pk__in=[c.pk for c in clones[1::2]]).update(
        statut='envoye', date_validite=timezone.localdate() + datetime.timedelta(days=3))
    apres = liste()
    ar2, ex2 = autres()
    pr2 = proposal(d_demo.id)
    # Montants : total_ttc servi par la liste = Devis.total_ttc relu SANS préchargement (chemin non optimisé).
    ecarts = []
    for ps in (5, 50):
        for did, v in apres[ps]['ttc'].items():
            ref = Devis.objects.get(pk=did).total_ttc
            if v is None or abs(Decimal(str(v)) - Decimal(str(ref))) > Decimal('0.01'):
                ecarts.append((did, v, str(ref)))
    out['liste'] = {'avant': {k: {x: v[x] for x in ('st', 'q', 'o', 'n')} for k, v in avant.items()},
                    'apres': {k: {x: v[x] for x in ('st', 'q', 'o', 'n')} for k, v in apres.items()}}
    ok['liste_200'] = all(v['st'] == 200 for v in list(avant.values()) + list(apres.values()))
    ok['liste_pente_page'] = _plat(apres[5]['q'], apres[50]['q']) and _plat(avant[5]['q'], avant[50]['q'])
    ok['liste_pente_donnees'] = _plat(avant[50]['q'], apres[50]['q'])
    ok['liste_sans_electrical_design'] = not any(v['ed'] for v in apres.values())
    ok['montants_liste_egaux_modele'] = not ecarts
    out['ecarts_montants'] = ecarts[:5]
    out['action_requise'] = {'avant': ar1, 'apres': ar2}
    ok['action_requise_200'] = ar1['st'] == 200 and ar2['st'] == 200
    ok['action_requise_plate'] = _plat(ar1['q'], ar2['q'])
    ok['action_requise_compteurs'] = (ar2['cpt'].get('refuses_sans_motif', 0) - ar1['cpt'].get('refuses_sans_motif', 0) == 10
                                      and ar2['cpt'].get('expirant_bientot', 0) - ar1['cpt'].get('expirant_bientot', 0) == 10)
    out['export_devis'] = {'avant': ex1, 'apres': ex2}
    ok['export_200'] = ex1['st'] == 200 and ex2['st'] == 200
    ok['export_plat'] = _plat(ex1['q'], ex2['q'])
    out['proposal'] = {'devis': d_demo.reference, 'avant': pr1, 'apres': pr2}
    ok['proposal_identique'] = (pr1.get('st') == 200 and pr1.get('pages') == pr2.get('pages')
                                and pr1.get('montants') == pr2.get('montants'))
    ok['zero_503'] = 503 not in [v['st'] for v in list(avant.values()) + list(apres.values())] + [
        ar1['st'], ar2['st'], ex1['st'], ex2['st'], pr1.get('st'), pr2.get('st')]
    return {'repro': all(ok.values()), 'ok': ok, **out}
