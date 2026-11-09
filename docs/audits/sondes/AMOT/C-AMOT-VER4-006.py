# flake8: noqa  (sonde de contre-visite vérifie AMOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""AMOT17 + AMOT18 (clause client « le client d'un autre installateur n'est jamais renvoyé vers TAQINOR ») : société
IDENTIFIÉE (nom + ICE ; ni RIB, ni banque, ni e-mail, ni téléphone, ni site), devis résidentiel deux options,
rendus /proposal réels : full + étude + devis final, une-page + devis final ; commercial full. Texte extrait (PyMuPDF)
cherché pour RIB/banque/contact/site TAQINOR ; contexte de chaque « taqinor » restant (logo, garantie de pose = hors
périmètre white-label). Transaction annulée."""
SONDE = {"constat": "C-AMOT-VER4-006", "sha": "c38868a62",
         "attendu": "0 occurrence de 0002720029379418, Saham, contact@taqinor, 61 85 04 10, taqinor.ma dans les 3 rendus ; "
                    "« Virement bancaire » absent ; nom de la société imprimé",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink", "parametres.CompanyProfile",
                     "authentication.Company"]}


def sonde(ctx):
    import re
    import fitz
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.parametres.models import CompanyProfile
    from apps.ventes.models import Devis
    from apps.ventes.tests._quote_engine_common import make_client, make_company, make_devis
    co = make_company(slug='sonde-amot-ver4-006', nom='SONDE VER4 006')
    p = CompanyProfile.get(company=co)
    CompanyProfile.objects.filter(pk=p.pk).update(nom='PROBE N1 SARL', ice='003333333000033', rib='', banque='',
                                                  email='', telephone='', site_web='')
    adm = get_user_model().objects.create_user(username='sonde-ver4-006', password='x', company=co,
                                               is_superuser=True, is_staff=True)
    api = APIClient(); api.force_authenticate(adm)
    cl = make_client(co)
    INTERDITS = ('0002720029379418', 'saham', 'contact@taqinor', '61 85 04 10', 'taqinor.ma', 'virement bancaire')
    out, ok = {}, True
    cas = []
    dr = make_devis(co, adm, cl, [('Panneau mono 550W', '14', '1100'), ('Onduleur réseau 10kW', '1', '11700'),
                                  ('Onduleur hybride 5kW', '1', '24000'), ('Batterie 5 kWh', '1', '14000')],
                    reference='DEV-SONDE-V4-006-R',
                    etude_params={'scenario': 'Les deux (Sans + Avec)', 'factures_mensuelles_reelles': [1500] * 12})
    cas += [('res_full_etude_final', dr, '?include_etude=1&devis_final=1'), ('res_onepage_final', dr, '?pdf_mode=onepage&devis_final=1')]
    dm = make_devis(co, adm, cl, [('Panneau mono 550W', '12', '1100'), ('Onduleur réseau 5kW', '1', '11700')],
                    reference='DEV-SONDE-V4-006-M',
                    etude_params={'scenario': 'Sans batterie', 'economies_annuelles': 9000, 'production_annuelle': 9500})
    cas.append(('mono_full_etude_final', dm, '?include_etude=1&devis_final=1'))
    dc = make_devis(co, adm, cl, [('Panneau mono 550W', '30', '1100'), ('Onduleur réseau 20kW', '1', '21700')],
                    reference='DEV-SONDE-V4-006-C')
    Devis.objects.filter(pk=dc.pk).update(mode_installation='commercial')
    cas.append(('commercial_full_final', dc, '?devis_final=1'))
    for nom, dv, qs in cas:
        rep = api.get(f'/api/django/ventes/devis/{dv.id}/proposal/{qs}', HTTP_HOST='localhost')
        body = b''.join(rep.streaming_content) if getattr(rep, 'streaming', False) else rep.content
        if rep.status_code != 200:
            out[nom] = {'http': rep.status_code, 'corps': (rep.content or b'')[:200].decode('utf-8', 'replace')}
            continue
        doc = fitz.open(stream=body, filetype='pdf')
        t = re.sub(r'[   ]', ' ', '\n'.join(pg.get_text() for pg in doc))
        bas = t.lower()
        liens = sorted({l.get('uri', '') for pg in doc for l in pg.get_links() if l.get('uri')})
        r = {'pages': doc.page_count, 'societe': 'probe n1 sarl' in bas,
             'interdits': {i: bas.count(i) for i in INTERDITS if i in bas},
             'liens_taqinor': [u for u in liens if 'taqinor' in u.lower()][:5],
             'contextes_taqinor': [t[max(0, m.start() - 50):m.end() + 30].replace('\n', ' | ')
                                   for m in re.finditer('(?i)taqinor', t)][:6]}
        ok &= not r['interdits'] and r['societe'] and not r['liens_taqinor']
        out[nom] = r
    out['repro'] = bool(ok)
    return out
