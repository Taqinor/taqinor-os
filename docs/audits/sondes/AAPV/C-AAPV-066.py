# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K12 — sur un BCF brouillon en devise, l'écran (`BonsCommandeFournisseur.jsx::buildPayload`) n'envoie que
`prix_achat_unitaire` (MAD) : `_upsert_lignes` reprend `prix_achat_unitaire_devise` de la base puis
`apply_devise_ligne_bcf` ÉCRASE le MAD saisi. Chaîne : POST BCF EUR taux 10,8, 10 × 100 EUR (1 080 MAD) ;
PATCH exactement comme l'écran (en-tête + lignes [{id, produit, designation:'', quantite, prix_achat_unitaire:1000}]).
(T) témoin : même PATCH sur un BCF en MAD → 1 000 gardé. Attendu sain : 1 000 MAD gardé (PU devise ≈ 92,59)
ou refus explicite."""
SONDE = {"constat": "C-AAPV-066", "sha": "6ffa876688",
         "attendu": "repro si PATCH 200 et PU MAD relu 1080 (saisie 1000 écrasée en silence) ; témoin MAD : 1000",
         "modeles": ["achats.BonCommandeFournisseur", "achats.LigneBonCommandeFournisseur"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur, BonCommandeFournisseur
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 066', slug='sonde-aapv-066')
    u = get_user_model().objects.create_user(username='sonde_aapv_066', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV66')
    p = Produit.objects.create(company=co, nom='Batterie AAPV66', sku='AAPV-066', prix_vente=Decimal('3000'),
                               prix_achat=Decimal('1000'), quantite_stock=0)
    url = '/api/django/stock/bons-commande-fournisseur/'

    def cycle(entete_devise):
        corps = {'fournisseur': f.id, 'lignes': [{'produit': p.id, 'quantite': 10, 'prix_achat_unitaire': 1080}]}
        if entete_devise:
            corps.update({'devise': 'EUR', 'taux_change': '10.8'})
            corps['lignes'][0]['prix_achat_unitaire_devise'] = '100'
        r = api.post(url, corps, format='json', **H)
        assert r.status_code == 201, (r.status_code, r.data)
        bid = r.data['id']
        bc = BonCommandeFournisseur.objects.get(pk=bid)
        l = bc.lignes.first()
        avant = str(l.prix_achat_unitaire)
        ecran = {'fournisseur': f.id, 'date_commande': None, 'date_livraison_prevue': None, 'note': None,
                 'acheteur': None, 'ref_fournisseur': None, 'note_bas_page': None, 'incoterm': None,
                 'lignes': [{'id': l.id, 'produit': p.id, 'designation': '', 'quantite': 10,
                             'prix_achat_unitaire': 1000}]}
        rp = api.patch(f'{url}{bid}/', ecran, format='json', **H)
        l.refresh_from_db()
        bc.refresh_from_db()
        return {'pu_avant': avant, 'patch_http': rp.status_code,
                'detail': None if rp.status_code < 400 else str(rp.data)[:140],
                'reponse_pu': (rp.data.get('lignes') or [{}])[0].get('prix_achat_unitaire') if rp.status_code == 200 else None,
                'pu_relu': str(l.prix_achat_unitaire), 'pu_devise_relu': str(l.prix_achat_unitaire_devise),
                'total_achat': str(bc.total_achat)}

    obs = {'T_mad': cycle(False), 'R_eur': cycle(True)}
    print(obs)
    temoin_ok = obs['T_mad']['patch_http'] == 200 and Decimal(obs['T_mad']['pu_relu']) == Decimal('1000')
    defaut = obs['R_eur']['patch_http'] == 200 and Decimal(obs['R_eur']['pu_relu']) == Decimal('1080')
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
