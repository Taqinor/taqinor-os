# flake8: noqa  (sonde de vérification C-L3-2, rejouable par scripts/sonde.py)
"""C-L3-2 — case L-SECT « Synthèse d'économies » décochée (`sections={'economies': False}`, PDF laissé coché) :
la charge JSON retire les économies, mais le PDF public du MÊME jeton (`/public/proposal/<t>/pdf/` et
`/public/document/<t>/`) les imprime-t-il ? Devis résidentiel 2 options ancré sur 12 factures (fixture ADEV50).
Rendu RÉEL (moteur + MinIO), texte extrait par PyMuPDF, comparé à un lien témoin (cases toutes cochées).
Options passées au moteur espionnées. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-023", "sha": "1dfa7986c",
         "attendu": "economies décochée : aucun chiffre d'économie dans le PDF public (défaut : mêmes chiffres que le témoin)",
         "modeles": ["ventes.Devis", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    import re
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    from apps.ventes import public_views
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.quote_engine.residential.renderer import synthese_economies
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 023', slug='sonde-advs-023')
    u = U.objects.create_user(username='sonde-advs-023', password='x', company=c)
    cl = Client.objects.create(company=c, nom='Client sections', email='sonde-advs-023@example.invalid')
    d = Devis.objects.create(company=c, reference='DEV-ADVS023-01', client=cl, taux_tva=Decimal('20'),
                             statut='envoye', created_by=u,
                             etude_params={'scenario': 'Les deux (Sans + Avec)',
                                           'factures_mensuelles_reelles': [1800] * 12,
                                           'distributeur': 'onee', 'ville': 'casablanca'})
    for i, (nom, q, pu) in enumerate((('Panneau Canadien Solar 710W', '14', '1166.67'),
                                      ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
                                      ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
                                      ('Batterie Dyness 10 kWh', '1', '25000.00'))):
        p = Produit.objects.create(company=c, nom=nom, sku=f'ADVS023-{i}', prix_vente=Decimal(pu), quantite_stock=50)
        LigneDevis.objects.create(devis=d, produit=p, designation=nom, quantite=Decimal(q), prix_unitaire=Decimal(pu),
                                  remise=Decimal('0'), ordre=i)
    obs = {}
    try:
        with transaction.atomic():
            synth = synthese_economies(build_quote_data(d, {'pdf_mode': 'full'}))
    except Exception as e:
        synth = None
        obs['synth_err'] = repr(e)[:160]
    if not synth:
        obs['synth'] = None
        return {'repro': False, 'observe': obs}
    ab, aa, pct = int(round(synth['annual_before'])), int(round(synth['annual_after'])), synth['pct_cut']
    eco = int(round(synth['eco_mensuelles_total']))
    obs['synth'] = {'annual_before': ab, 'annual_after': aa, 'pct_cut': pct, 'eco_annuelle': eco}

    def marqueurs(pdf):
        try:
            import fitz
            doc = fitz.open(stream=pdf, filetype='pdf')
            txt = '\n'.join(p.get_text() for p in doc)
            pages = doc.page_count
        except Exception as e:
            return {'err': repr(e)[:120]}
        plat = re.sub(r'[\s   .,]', '', txt)
        return {'pages': pages, 'annual_before': str(ab) in plat, 'annual_after': str(aa) in plat,
                'eco_annuelle': str(eco) in plat, 'pct_cut': bool(re.search(r'[-−–]\s*%d\s*%%' % pct, txt)),
                'mot_economie': len(re.findall(r'[ÉéEe]conomi', txt))}

    vrai = public_views.generate_premium_devis_pdf
    opts_vues = []

    def espion(devis_id, opts, **k):
        opts_vues.append(sorted((opts or {}).keys()))
        return vrai(devis_id, opts, **k)

    def lire(sections, etiquette):
        link = ShareLink.objects.create(company=c, devis=d, sections=sections)
        o = {'sections': sections}
        pub = APIClient()
        with mock.patch('apps.ventes.public_views._notify_open'), \
                mock.patch.object(public_views, 'generate_premium_devis_pdf', side_effect=espion):
            for nom, url in (('data', f'/api/django/public/proposal/{link.token}/data/'),
                             ('pdf', f'/api/django/public/proposal/{link.token}/pdf/'),
                             ('document', f'/api/django/public/document/{link.token}/')):
                try:
                    with transaction.atomic():
                        r = pub.get(url, HTTP_HOST='localhost')
                    brut = r.content if hasattr(r, 'content') else b''.join(r.streaming_content)
                except Exception as e:
                    o[nom] = repr(e)[:160]
                    continue
                if nom == 'data':
                    j = json.loads(brut.decode('utf-8', 'replace') or '{}')
                    o['data'] = [r.status_code, {k: j.get(k) for k in ('pct_cut', 'annual_before', 'annual_after',
                                                                        'pdf_disponible')}]
                else:
                    o[nom] = [r.status_code, marqueurs(brut) if brut[:4] == b'%PDF' else brut[:120].decode('latin-1')]
        return o

    obs['temoin_tout_coche'] = lire({}, 'T')
    obs['economies_decochee'] = lire({'economies': False}, 'E')
    obs['opts_moteur'] = opts_vues[:2]
    e = obs['economies_decochee']
    pdf = e.get('pdf') if isinstance(e.get('pdf'), list) else [None, {}]
    m = pdf[1] if isinstance(pdf[1], dict) else {}
    repro = bool(pdf[0] == 200 and (m.get('annual_before') or m.get('eco_annuelle') or m.get('pct_cut')))
    return {'repro': repro, 'observe': obs}
