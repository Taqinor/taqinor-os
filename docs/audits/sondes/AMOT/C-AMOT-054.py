SONDE = {"constat": "C-AMOT-054", "sha": "673ec3f92",
         "attendu": "P3.4 — devis AGRICOLE de la société anonymisée (anon_admin ; aucun devis démo n'a de point d'eau "
                    "mesuré : la provenance du niveau statique et de la HMT saisie passe à « mesure_visite » dans la "
                    "transaction, structure réelle du producteur) : synthese_agricole.provenance les porte (liste "
                    "blanche, sans _empreinte), elles sortent de a_confirmer_par_visite ; le PDF imprime « mesuré par "
                    "<société> » ; 3 pages, 4 avec la note de calcul ; 0 onduleur, 0 batterie"}


def sonde(ctx):
    import copy
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.quote_engine.agricole.synthese import LISTE_BLANCHE_PROVENANCE, synthese_agricole
    H = {'HTTP_HOST': 'localhost'}
    user = get_user_model().objects.get(username='anon_admin')
    api = APIClient()
    api.force_authenticate(user)

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(did, qs=''):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    dv = next((d for d in Devis.objects.filter(company=user.company, mode_installation='agricole').order_by('-id')
               if 'hmt_saisie_m' in (((d.etude_params or {}).get('provenance_pompage') or {}).get('entrees') or {})
               and 'niveau_statique_m' in (((d.etude_params or {}).get('provenance_pompage') or {}).get('entrees')
                                           or {})), None)
    if dv is None:
        return {'repro': False, 'motif': 'aucun devis agricole avec provenance hmt_saisie_m + niveau_statique_m'}
    out, ok = {'devis': dv.reference}, True
    ep = copy.deepcopy(dv.etude_params)
    for cle in ('niveau_statique_m', 'hmt_saisie_m'):
        ep['provenance_pompage']['entrees'][cle].update({'origine': 'lead', 'detail': 'mesure_visite',
                                                         'date': '2026-10-20'})
    Devis.objects.filter(pk=dv.pk).update(etude_params=ep)
    dv.refresh_from_db()
    d = build_quote_data(dv, clean_pdf_options({}))
    s = synthese_agricole(d) or {}
    prov = s.get('provenance') or {}
    a_conf = s.get('a_confirmer_par_visite') or []
    out['synthese'] = {'provenance_cles': sorted(prov), 'a_confirmer': list(a_conf),
                       'niveau_statique': prov.get('niveau_statique_m'), 'hmt': prov.get('hmt_m')}
    ok &= (set(prov) <= set(LISTE_BLANCHE_PROVENANCE) and '_empreinte' not in prov
           and (prov.get('niveau_statique_m') or {}).get('detail') == 'mesure_visite'
           and (prov.get('hmt_m') or {}).get('detail') == 'mesure_visite'
           and 'niveau_statique_m' not in a_conf and 'hmt_m' not in a_conf)
    for nom, qs, pages_attendues in (('agricole', '', 3), ('agricole_note', '?include_note_calcul=1', 4)):
        st, txt, pages = lire(dv.id, qs)
        bas = txt.lower()
        res = {'http': st, 'pages': pages, 'mesure_par': [ln for ln in txt.splitlines() if 'mesuré par' in ln][:3],
               'onduleur': bas.count('onduleur'), 'batterie': bas.count('batterie')}
        out[nom] = res
        ok &= st == 200 and pages == pages_attendues
        if nom == 'agricole_note':
            ok &= bool(res['mesure_par'])
    tous = [it.get('designation', '') for it in d.get('all_items', [])]
    out['lignes'] = {'onduleur': [x for x in tous if 'onduleur' in x.lower()],
                     'batterie': [x for x in tous if 'batterie' in x.lower()]}
    ok &= not out['lignes']['onduleur'] and not out['lignes']['batterie']
    out['repro'] = bool(ok)
    return out
