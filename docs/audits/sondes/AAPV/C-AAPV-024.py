# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K26 — la quarantaine de réception non conforme (NTWMS34, `router_apres_controle`) est posée SANS lot :
« Sortir » ce lot (`lots-entrepot/<id>/sortir/`, garde ASTK199 = blocages AVEC lot seulement) la contourne.
(R) catégorie sous plan d'échantillonnage, réception 10 cartouches lot L-77 (vraie route), verdict NON CONFORME,
`confirmer/` → blocage 10 ; POST lots-entrepot/<L-77>/sortir/ {quantite: 10}.
(T) témoin : même lot mis en quarantaine AVEC le lot (`mettre_en_quarantaine(lot=…)`, chemin du rappel ASTK199)
→ la même sortie est refusée 409."""
SONDE = {"constat": "C-AAPV-024", "sha": "b432084786",
         "attendu": "repro si R : sortir 200, stock 0, lot 0, blocage 10 toujours en quarantaine ; T : 409",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.LotEntrepot", "stock.BlocageQualite"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, Categorie, PlanEchantillonnage, BlocageQualite, LotEntrepot)
    from apps.stock.services_wms import mettre_en_quarantaine
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 024', slug='sonde-aapv-024')
    u = get_user_model().objects.create_user(username='sonde_aapv_024', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cat = Categorie.objects.create(company=co, nom='Étanchéité AAPV24')
    PlanEchantillonnage.objects.create(company=co, categorie=cat, taux_echantillon_pct=20)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV24')
    url = '/api/django/stock/receptions-fournisseur/'

    def recevoir(n, verdict):
        p = Produit.objects.create(company=co, nom=f'Cartouche AAPV24-{n}', sku=f'AAPV-024-{n}', categorie=cat,
                                   prix_vente=Decimal('80'), prix_achat=Decimal('50'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-024-{n}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('50'))
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10,
                                                              'numero_lot': f'L-77-{n}'}]}, format='json', **H)
        rid = r.data['id']
        rq = api.post(f'{url}{rid}/controle-qualite/', {'resultat': verdict, 'unites_controlees': 2},
                      format='json', **H)
        rc = api.post(f'{url}{rid}/confirmer/', {}, format='json', **H)
        lot = LotEntrepot.objects.get(company=co, produit=p)
        return p, lot, {'creation': r.status_code, 'controle': rq.status_code, 'confirmer': rc.status_code}

    def etat(p, lot):
        p.refresh_from_db()
        lot.refresh_from_db()
        return {'stock': p.quantite_stock, 'lot_restant': lot.quantite_restante,
                'blocages': list(BlocageQualite.objects.filter(company=co, produit=p).values_list(
                    'quantite', 'statut', 'lot_id'))}

    obs = {}
    p, lot, init = recevoir('R', 'non_conforme')
    avant = etat(p, lot)
    rs = api.post(f'/api/django/stock/lots-entrepot/{lot.id}/sortir/', {'quantite': 10}, format='json', **H)
    obs['R'] = {'init': init, 'avant': avant, 'sortir': rs.status_code,
                'detail': None if rs.status_code < 400 else str(rs.data)[:160], 'apres': etat(p, lot)}
    pT, lotT, initT = recevoir('T', 'conforme')
    mettre_en_quarantaine(company=co, produit=pT, quantite=10, user=u, lot=lotT, motif='rappel témoin')
    rsT = api.post(f'/api/django/stock/lots-entrepot/{lotT.id}/sortir/', {'quantite': 10}, format='json', **H)
    obs['T'] = {'init': initT, 'sortir': rsT.status_code,
                'detail': None if rsT.status_code < 400 else str(rsT.data)[:160], 'apres': etat(pT, lotT)}
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = t['sortir'] == 409 and t['apres']['stock'] == 10
    defaut = (r['avant']['blocages'] and r['avant']['blocages'][0][2] is None and r['sortir'] == 200
              and r['apres']['stock'] == 0 and r['apres']['lot_restant'] == 0
              and any(st == 'en_quarantaine' for _, st, _l in r['apres']['blocages']))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
