# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K27 — un plan d'échantillonnage (écran Qualité & rappels) bloque TOUTE réception du produit tant qu'aucun
`ControleReception` n'existe ; le verdict ne se saisit que par `POST receptions-fournisseur/<id>/controle-qualite/`,
qu'aucun écran n'appelle (grep frontend). Vraies routes : (1) « Recevoir les quantités » du BCF
(`bons-commande-fournisseur/<id>/recevoir/`, crée ET confirme dans une transaction : aucun contrôle possible)
→ 400 ; (2) réception brouillon (`receptions-fournisseur/`) puis `confirmer/` → 400. Témoin : l'API seule
(`controle-qualite/` conforme) débloque la confirmation (200)."""
SONDE = {"constat": "C-AAPV-105", "sha": "c6bd9b5d52",
         "attendu": "repro si recevoir/ 400 et confirmer/ 400 (message contrôle qualité), puis controle-qualite 200 + confirmer 200",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.BonCommandeFournisseur", "stock.PlanEchantillonnage", "stock.ControleReception"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit,
                                   Categorie, PlanEchantillonnage)
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 105', slug='sonde-aapv-105')
    u = get_user_model().objects.create_user(username='sonde_aapv_105', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cat = Categorie.objects.create(company=co, nom='Batteries S105')
    PlanEchantillonnage.objects.create(company=co, categorie=cat, taux_echantillon_pct=10, actif=True)
    p = Produit.objects.create(company=co, nom='Batterie S105', sku='AAPV-105', prix_vente=Decimal('5000'),
                               quantite_stock=0, categorie=cat)
    f = Fournisseur.objects.create(company=co, nom='F-S105')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-S105',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('3000'))
    rv = api.post(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/recevoir/',
                  {'receptions': [{'ligne': lc.id, 'quantite': 5}]}, format='json', **H)
    p.refresh_from_db()
    obs = {'recevoir_http': rv.status_code, 'recevoir_detail': str(getattr(rv, 'data', ''))[:160],
           'stock_apres_recevoir': p.quantite_stock}
    url = '/api/django/stock/receptions-fournisseur/'
    r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 5}]},
                 format='json', **H)
    rid = r.data.get('id') if r.status_code < 400 else None
    ech = api.get(f'{url}{rid}/echantillonnage/', **H) if rid else None
    c1 = api.post(f'{url}{rid}/confirmer/', {}, format='json', **H) if rid else None
    obs.update({'creer_reception_http': r.status_code,
                'echantillonnage': None if ech is None else ech.data,
                'confirmer_http': None if c1 is None else c1.status_code,
                'confirmer_detail': None if c1 is None else str(getattr(c1, 'data', ''))[:160]})
    # témoin : la saisie API du verdict débloque
    cq = api.post(f'{url}{rid}/controle-qualite/', {'resultat': 'conforme', 'unites_controlees': 1},
                  format='json', **H) if rid else None
    c2 = api.post(f'{url}{rid}/confirmer/', {}, format='json', **H) if rid else None
    p.refresh_from_db()
    obs.update({'controle_qualite_http': None if cq is None else cq.status_code,
                'confirmer_apres_controle_http': None if c2 is None else c2.status_code,
                'stock_final': p.quantite_stock})
    print(obs)
    temoin_ok = cq is not None and cq.status_code == 200 and c2.status_code == 200 and p.quantite_stock == 5
    defaut = rv.status_code == 400 and c1 is not None and c1.status_code == 400 \
        and 'contrôle qualité' in obs['confirmer_detail']
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
