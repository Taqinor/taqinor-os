SONDE = {"constat": "C-APRF-ACC-VENTES-PILES", "sha": "665a4ce53", "attendu": "Diagnostic de C-APRF-ACC-VENTES : piles d appel (execute_wrapper) des requêtes répétées par ligne sur GET ventes/devis/?page_size=5 de la société 4 ; attendu (pente nulle) : aucune pile répétée par ligne", "modeles": ["ventes.Devis"]}
H = {'HTTP_HOST': 'localhost'}


def sonde(ctx):
    import os
    import re
    import traceback
    from collections import Counter
    from django.db import connection
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    U = get_user_model()
    u = U.objects.filter(company_id=4, is_active=True).order_by('id').first()
    api = APIClient()
    api.force_authenticate(u)
    out = ['cwd=%s' % os.getcwd()]
    src = open('apps/crm/lead_devis_payload.py', encoding='utf-8').read() if os.path.exists('apps/crm/lead_devis_payload.py') else ''
    out.append('PREFETCH_DEVIS_LISTE_LEADS present=%s' % ('PREFETCH_DEVIS_LISTE_LEADS' in src))
    piles = Counter()

    def wrap(execute, sql, params, many, context):
        m = re.search(r'FROM\s+"(\w+)"', sql)
        t = m.group(1) if m else '?'
        if t in ('parametres_tariffsettings', 'crm_visiteterrain', 'ventes_lignedevis', 'parametres_companyprofile', 'crm_leadactivity'):
            fr = [f for f in traceback.extract_stack() if '/apps/' in f.filename or '/core/' in f.filename]
            pile = ' < '.join('%s:%s:%s' % (f.filename.split('/django_core/')[-1].replace('/app/', ''), f.lineno, f.name) for f in reversed(fr[-6:]))
            piles[t + ' :: ' + pile] += 1
        return execute(sql, params, many, context)
    with connection.execute_wrapper(wrap):
        r = api.get('/api/django/ventes/devis/', {'page_size': 5}, **H)
    for k, v in piles.most_common(14):
        out.append('%3d %s' % (v, k[:420]))
    return '\n'.join(out)[:5900]
