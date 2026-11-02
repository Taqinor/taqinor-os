# flake8: noqa  (sonde de vérification C-L1-3, rejouable par scripts/sonde.py)
"""C-L1-3 — la garde « kWh déclaré vs factures » (règle fondateur 30/09) n'est pas appliquée par POST
devis/from-layout/ : un lead à 46 kWh/mois déclarés et 10 000 MAD de facture d'hiver reçoit un brouillon
chiffré (201), alors que POST devis/atomic/ sur le même lead répond 409 kwh_incoherent_factures.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ADVS-003", "sha": "1dfa7986c",
         "attendu": "from-layout → 409 kwh_incoherent_factures, 0 devis (défaut : 201 + brouillon chiffré)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes.etude_horaire import controle_kwh_declare_du_lead
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 003', slug='sonde-advs-003')
    u = U.objects.create_user(username='sonde-advs-003', password='x', role_legacy='responsable', company=c)
    lead = Lead.objects.create(company=c, nom='Kwh', prenom='Incoherent', email='sonde-advs-003@example.invalid',
                               telephone='+212600003003', ville='Casablanca',
                               conso_mensuelle_kwh=46, facture_hiver=Decimal('10000'))
    prods = {}
    for nom, sku, prix in (('Panneau Jinko 550W', 'ADVS003-PAN', '1100'),
                           ('Onduleur réseau Huawei 5kW Monophasé', 'ADVS003-OND', '14000'),
                           ('Onduleur hybride Deye 5kW Monophasé', 'ADVS003-HYB', '17000'),
                           ('Batterie Dyness 5 kWh', 'ADVS003-BAT', '16000')):
        prods[sku] = Produit.objects.create(company=c, nom=nom, sku=sku, prix_vente=Decimal(prix),
                                            prix_achat=Decimal('1'), tva=Decimal('20'), quantite_stock=100)
    ctl = controle_kwh_declare_du_lead(lead, c)
    obs = {'controle_lead': {k: (ctl or {}).get(k) for k in ('coherent', 'ratio', 'kwh_factures', 'kwh_declare')}
           if isinstance(ctl, dict) else str(ctl)}
    api = APIClient()
    api.force_authenticate(u)

    def appel(url, corps):
        try:
            with transaction.atomic():
                r = api.post(url, corps, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace')
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    layout = {'scenario': 'reseau', 'panelWatt': 550,
              'result': {'panels': 8, 'kwc': 4.4, 'annualKwh': 7200, 'savings': 6000}}
    s1, r1 = appel('/api/django/ventes/devis/from-layout/', {'layout': layout, 'lead': lead.id})
    dv = Devis.objects.filter(company=c, lead=lead).first()
    obs['from_layout'] = {'http': s1, 'reponse': {k: r1.get(k) for k in ('id', 'reference', 'statut', 'detail', 'code')},
                          'devis_crees': Devis.objects.filter(company=c, lead=lead).count(),
                          'total_ttc': str(dv.total_ttc) if dv else None,
                          'nb_lignes': dv.lignes.count() if dv else None}
    if dv is not None:
        try:
            from apps.crm.selectors import conso_mensuelle_kwh_pour_devis
            obs['kwh_lu_par_etudes'] = str(conso_mensuelle_kwh_pour_devis(dv))
        except Exception as e:
            obs['kwh_lu_par_etudes'] = repr(e)[:120]
        ep = dv.etude_params or {}
        obs['etude_params'] = {k: ep[k] for k in list(ep)[:40] if not isinstance(ep[k], (dict, list))}
        try:
            from apps.ventes.quote_engine.builder import build_quote_data
            with transaction.atomic():
                d = build_quote_data(dv)
            obs['pdf_conso_economie'] = {k: d.get(k) for k in d if any(m in k.lower() for m in ('conso', 'econom', 'saving', 'couvert', 'autoconso', 'bill', 'facture'))
                                         and not isinstance(d.get(k), (dict, list))}
        except Exception as e:
            obs['pdf_conso_economie'] = repr(e)[:200]
    s2, r2 = appel('/api/django/ventes/devis/atomic/', {
        'lead': lead.id, 'taux_tva': '20.00',
        'lignes': [{'produit': prods['ADVS003-PAN'].id, 'designation': 'Panneau Jinko 550W', 'quantite': '8',
                    'prix_unitaire': '1100.00', 'taux_tva': '20'}]})
    obs['atomic_meme_lead'] = {'http': s2, 'detail': str(r2.get('detail'))[:160], 'code': r2.get('code')}
    # le brouillon né de from-layout : replace-lines (ré-enregistrement depuis le générateur)
    if dv is not None:
        s3, r3 = appel(f'/api/django/ventes/devis/{dv.id}/replace-lines/', {
            'lignes': [{'produit': prods['ADVS003-PAN'].id, 'designation': 'Panneau Jinko 550W', 'quantite': '8',
                        'prix_unitaire': '1100.00', 'taux_tva': '20'}]})
        obs['replace_lines_du_brouillon'] = {'http': s3, 'detail': str(r3.get('detail'))[:160], 'code': r3.get('code')}
    repro = s1 in (200, 201) and obs['from_layout']['devis_crees'] == 1 and s2 == 409
    return {'repro': repro, 'observe': obs}
