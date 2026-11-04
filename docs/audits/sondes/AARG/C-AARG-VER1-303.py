# flake8: noqa  (sonde de contre-visite VER1 lot 3 — AARG36, rejouable par scripts/sonde.py)
"""AARG36 (C-AARG-039) : un avoir et une note de débit sur une facture émise 10 % / 20 % montrent leurs deux
« Base HT » ; l'avoir porte « Facture d'origine FA-… du JJ/MM/AAAA ». Chemin RÉEL : facture émise par l'API
(2 lignes 1 000 HT à 10 % et à 20 %), avoir TOTAL (`creer-avoir`), avoir PARTIEL à 2 lignes (`lignes`), note de
débit à 2 lignes (`creer-note-debit`), puis `generate_*_pdf` (WeasyPrint réel, upload capturé) et lecture du texte
PDF par PyMuPDF. `repro` = vrai quand un attendu est faux. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-039", "sha": "06ced8b1a",
         "attendu": "avoir total, avoir partiel 2 taux, ND 2 taux : « Base HT (10…%) 1000.00 » et « Base HT (20…%) 1000.00 » dans le texte du PDF ; avoir : « <réf facture> du <date émission> »",
         "modeles": ["authentication.Company", "ventes.Facture", "ventes.Avoir", "ventes.NoteDebit"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    from unittest.mock import patch
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Avoir, Facture, LigneFacture, NoteDebit
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.utils import pdf as pdfmod
    import fitz
    co = Company.objects.create(nom='Sonde VER1-303', slug='sonde-ver1-303')
    u = get_user_model().objects.create_user(username='sonde-v303', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Idrissi', prenom='Nadia', email='v303@example.invalid',
                               telephone='+212600000303')
    p10 = Produit.objects.create(company=co, nom='Cable', sku='SONDE-V303-10', prix_vente=Decimal('1000'), quantite_stock=100)
    p20 = Produit.objects.create(company=co, nom='Kit', sku='SONDE-V303-20', prix_vente=Decimal('1000'), quantite_stock=100)
    f = Facture.objects.create(company=co, reference='BROUILLON-SONDE-V303', client=cl, statut=Facture.Statut.BROUILLON,
                               taux_tva=Decimal('20'))
    LigneFacture.objects.create(facture=f, produit=p10, designation='Cable', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('10'))
    LigneFacture.objects.create(facture=f, produit=p20, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    emettre_facture(Facture.objects.get(pk=f.pk), source='sonde')
    f = Facture.objects.get(pk=f.pk)
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    H = dict(HTTP_HOST='localhost', format='json')
    obs = {'facture': (f.reference, str(f.total_ttc), str(f.date_emission), f.statut)}

    def texte(generer, pk):
        boite = {}
        with patch.object(pdfmod, '_upload_pdf', side_effect=lambda b, k: boite.__setitem__('pdf', b)), \
                patch.object(pdfmod, '_download', return_value=None):
            generer(pk)
        with fitz.open(stream=boite['pdf'], filetype='pdf') as doc:
            return re.sub(r'\s+', ' ', '\n'.join(pg.get_text() for pg in doc))

    def bases(t):
        return {'10': bool(re.search(r'Base HT \(10(\.0+)?%\) 1000\.00 MAD', t)),
                '20': bool(re.search(r'Base HT \(20(\.0+)?%\) 1000\.00 MAD', t))}

    # 1. avoir total
    r = api.post(f'{B}/factures/{f.id}/creer-avoir/', {'motif': 'Sonde'}, **H)
    obs['1_avoir_total_http'] = r.status_code
    av = Avoir.objects.filter(facture=f).order_by('-pk').first()
    if av:
        t = texte(pdfmod.generate_avoir_pdf, av.id)
        obs['1_avoir_total_ventilation_tva'] = av.ventilation_tva
        obs['1_avoir_total_bases'] = bases(t)
        d = f.date_emission.strftime('%d/%m/%Y')
        obs['1_avoir_total_origine'] = bool(re.search(re.escape(f.reference) + r'\s+du\s+' + re.escape(d), t))
        obs['1_extrait'] = t[t.find('Facture d'):t.find('Facture d') + 120] if 'Facture d' in t else None
        # annuler l'avoir pour pouvoir en créer un partiel
        api.post(f'{B}/avoirs/{av.id}/annuler/', {}, **H)
    # 2. avoir partiel à 2 lignes
    lignes = [{'produit': p10.id, 'designation': 'Cable', 'quantite': '1', 'prix_unitaire': '1000', 'taux_tva': '10'},
              {'produit': p20.id, 'designation': 'Kit', 'quantite': '1', 'prix_unitaire': '1000', 'taux_tva': '20'}]
    r = api.post(f'{B}/factures/{f.id}/creer-avoir/', {'motif': 'Sonde partiel', 'lignes': lignes}, **H)
    obs['2_avoir_partiel_http'] = (r.status_code, None if r.status_code < 400 else r.data)
    av2 = Avoir.objects.filter(facture=f).order_by('-pk').first()
    if av2 and r.status_code < 400:
        t = texte(pdfmod.generate_avoir_pdf, av2.id)
        obs['2_avoir_partiel_ventilation_tva'] = av2.ventilation_tva
        obs['2_avoir_partiel_bases'] = bases(t)
    # 3. note de débit à 2 lignes
    r = api.post(f'{B}/factures/{f.id}/creer-note-debit/', {'motif': 'Sonde ND', 'lignes': lignes}, **H)
    obs['3_nd_http'] = (r.status_code, None if r.status_code < 400 else r.data)
    nd = NoteDebit.objects.filter(facture=f).order_by('-pk').first()
    if nd and r.status_code < 400:
        t = texte(pdfmod.generate_note_debit_pdf, nd.id)
        obs['3_nd_ventilation_tva'] = nd.ventilation_tva
        obs['3_nd_bases'] = bases(t)
    print(obs)
    manque = [k for k in ('1_avoir_total_bases', '2_avoir_partiel_bases', '3_nd_bases')
              if not (obs.get(k) and all(obs[k].values()))]
    if not obs.get('1_avoir_total_origine'):
        manque.append('1_avoir_total_origine')
    return {'repro': bool(manque), 'manque': manque, **obs}
