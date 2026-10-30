SONDE = {"constat": "C-AMOT-019", "sha": "673ec3f92",
         "attendu": "P3.1 — devis BAT-DIFF (deux options, option 2 = onduleur hybride SANS batterie chiffrée) : "
                    "libelle_avec serveur = « Hybride, batterie plus tard » ; PDF résidentiel 3 p., legacy étude + devis "
                    "final et une-page : 0 « avec batterie » (insensible à la casse), 0 « Stockage », libellé serveur "
                    "imprimé ; témoin : un devis à batterie réelle garde « Avec batterie »"}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
    from apps.ventes.tests._quote_engine_common import DEUX_OPTIONS, make_client, make_devis
    H = {'HTTP_HOST': 'localhost'}
    admin = get_user_model().objects.get(username='demo_admin')
    api = APIClient()
    api.force_authenticate(admin)
    co = admin.company

    def norm(t):
        return re.sub(r'[   ]', ' ', t or '')

    def lire(did, qs):
        r = api.get(f'/api/django/ventes/devis/{did}/proposal/{qs}', **H)
        if r.status_code != 200:
            return r.status_code, '', 0
        body = b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content
        doc = fitz.open(stream=body, filetype='pdf')
        return 200, norm('\n'.join(p.get_text() for p in doc)), doc.page_count

    cli = make_client(co)
    devis = make_devis(co, admin, cli, [('Panneau mono 550W', '14', '1100'), ('Onduleur réseau 10kW', '1', '11700'),
                                        ('Onduleur hybride 5kW', '1', '24000')],
                       reference='DEV-SONDE-AMOT019', etude_params=dict(DEUX_OPTIONS))
    temoin = make_devis(co, admin, cli, [('Panneau mono 550W', '14', '1100'), ('Onduleur réseau 10kW', '1', '11700'),
                                         ('Onduleur hybride 5kW', '1', '24000'), ('Batterie 5 kWh', '1', '14000')],
                        reference='DEV-SONDE-AMOT019-T', etude_params=dict(DEUX_OPTIONS))
    Devis.objects.filter(pk__in=[devis.pk, temoin.pk]).update(mode_installation='residentiel')
    out, ok = {}, True
    d = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
    lib = d.get('libelle_avec')
    out['serveur'] = {'libelle_avec': lib, 'nb_options': d.get('nb_options')}
    ok &= bool(lib) and 'batterie plus tard' in (lib or '').lower()
    for nom, qs in (('residentiel_3p', ''),
                    ('legacy_etude_final', '?include_etude=1&devis_final=1&include_calepinage=0'),
                    ('onepage', '?pdf_mode=onepage')):
        st, txt, pages = lire(devis.id, qs)
        bas = txt.lower()
        res = {'http': st, 'pages': pages, 'avec_batterie': bas.count('avec batterie'),
               'stockage': bas.count('stockage'), 'libelle_imprime': bool(lib) and lib.lower() in bas,
               'contexte': [ln for ln in txt.splitlines() if 'avec batterie' in ln.lower()
                            or 'stockage' in ln.lower()][:4]}
        out[nom] = res
        ok &= st == 200 and res['avec_batterie'] == 0 and res['stockage'] == 0 and res['libelle_imprime']
    st, txt, pages = lire(temoin.id, '')
    out['temoin_batterie_reelle'] = {'http': st, 'avec_batterie': 'Avec batterie' in txt}
    ok &= st == 200 and 'Avec batterie' in txt
    out['repro'] = bool(ok)
    return out
