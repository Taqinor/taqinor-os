# flake8: noqa  (sonde de session reprise telle quelle : style libre, logique validee le 09/10)
"""Sonde de la session audit-méthode du 09/10/2026 (R3), rejouable par scripts/sonde.py (AMET93) :
transaction annulée, mail en mémoire, Celery coupé, HTTP bloqué. Jamais contre la prod.
"""
SONDE = {
    'constat': 'C-AMET-009',
    'sha': 'f3716e3f0',
    'attendu': "shadeObstructions[].bout : GPS réel conservé par l'anonymisation ; recentrage 500 m → ombre 505,65 m",
}


def sonde(ctx):
    pass
    import json, math
    from apps.calepinage.dsr_provider import document_anonymise
    from apps.calepinage.services.repere import _translater_document, CHEMINS_TRANSLATES
    from apps.calepinage.services.translation_conception import translater_conception
    pin = {'lat': 33.5731, 'lng': -7.5898}
    doc = {
      'version': 2,
      'pin': dict(pin),
      'zones': [{'id': 'z1', 'vertices': [[-7.5899, 33.5730], [-7.5897, 33.5730], [-7.5897, 33.5732], [-7.5899, 33.5732]]}],
      'shadeObstructions': [{
         'id': 'o1', 'kind': 'ombre_tracee',
         'centre': [-7.58985, 33.57305],
         'bout':   [-7.58975, 33.57300],
         'rayonM': 0.5, 'hauteurM': 4.2, 'source': 'ombre_tracee'}],
    }
    print('bout_in_CHEMINS', any('bout' in k for k in CHEMINS_TRANSLATES))
    a = document_anonymise(doc)
    so = a['shadeObstructions'][0]
    print('ANON centre ->', so['centre'], '| bout ->', so['bout'], '| pin kept:', 'pin' in a, '| repere:', a.get('repere'))
    print('ANON bout unchanged (real GPS survives):', so['bout'] == doc['shadeObstructions'][0]['bout'])
    # re-centre: move 500 m north
    nouveau = {'lat': pin['lat'] + 500/111320.0, 'lng': pin['lng']}
    t = _translater_document(doc, pin, nouveau)
    st = t['shadeObstructions'][0]
    print('RECENTRE centre moved:', st['centre'] != doc['shadeObstructions'][0]['centre'], '| bout moved:', st['bout'] != doc['shadeObstructions'][0]['bout'])
    from core.calepinage.geo import projeteur_local
    p = projeteur_local((nouveau['lng'], nouveau['lat']))
    cx, cy = p(tuple(st['centre'])); bx, by = p(tuple(st['bout']))
    x0,y0 = projeteur_local((pin['lng'],pin['lat']))(tuple(doc['shadeObstructions'][0]['centre']))
    x1,y1 = projeteur_local((pin['lng'],pin['lat']))(tuple(doc['shadeObstructions'][0]['bout']))
    print('shadow length before (m): %.2f  after recentre (m): %.2f' % (math.hypot(x1-x0,y1-y0), math.hypot(bx-cx,by-cy)))
    try:
        tc = translater_conception(doc, nouveau)
        tc_doc = tc[0] if isinstance(tc, tuple) else tc
        if isinstance(tc_doc, dict) and tc_doc.get('shadeObstructions'):
            s2 = tc_doc['shadeObstructions'][0]
            print('TRANSLATER_CONCEPTION bout moved:', s2['bout'] != doc['shadeObstructions'][0]['bout'], '| centre moved:', s2['centre'] != doc['shadeObstructions'][0]['centre'])
        else:
            print('translater_conception returned', type(tc))
    except Exception as e:
        print('translater_conception error', type(e).__name__, e)
