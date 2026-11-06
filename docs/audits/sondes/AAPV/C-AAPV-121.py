# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""T3 (critique L3) — archiver un produit qui a du stock le sort de l'écran Valorisation
(`GET stock/produits/valorisation/`, modale de StockList.jsx) et du KPI dashboard (`GET reporting/dashboard/`),
alors que la valorisation à date (`GET stock/produits/valorisation-a-date/?date=<aujourd'hui>`, écran
Inventaires annuels → ValorisationADate.jsx) le garde : même jour, deux totaux. Portes d'archivage :
`DELETE stock/produits/<id>/` (bouton « Supprimer » de StockList.jsx::handleDelete) et `PATCH {is_archived}`.
P : 40 reçus @ 500 (valeur 20 000) ; R : 5 reçus @ 200 (1 000) archivé par PATCH ; Q témoin : 10 reçus @ 300 (3 000)."""
SONDE = {"constat": "C-AAPV-121", "sha": "acc21a69c0",
         "attendu": "repro si avant : valorisation == valorisation-a-date (24000) ; après DELETE P + PATCH R : valorisation 3000, a-date 24000, P.quantite_stock 40",
         "modeles": ["stock.Produit", "stock.MouvementStock", "achats.BonCommandeFournisseur",
                     "achats.ReceptionFournisseur"]}

H = {'HTTP_HOST': 'localhost'}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur
    from apps.achats.models import (BonCommandeFournisseur, LigneBonCommandeFournisseur, ReceptionFournisseur,
                                    LigneReceptionFournisseur)
    co = Company.objects.create(nom='Sonde AAPV 121', slug='sonde-aapv-121')
    u = get_user_model().objects.create_user(username='sonde_aapv_121', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV121')
    today = datetime.date.today()

    def produit_recu(tag, qte, pu, pv):
        p = Produit.objects.create(company=co, nom='Produit ' + tag, sku='S121-' + tag, prix_vente=Decimal(pv),
                                   quantite_stock=0, tva=Decimal('20.00'))
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-S121-' + tag,
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE, date_commande=today)
        lg = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=qte,
                                                        prix_achat_unitaire=Decimal(pu))
        r = ReceptionFournisseur.objects.create(company=co, reference='REC-S121-' + tag, bon_commande=bc,
                                                date_reception=today)
        LigneReceptionFournisseur.objects.create(reception=r, ligne_commande=lg, produit=p, quantite=qte)
        rr = api.post(f'/api/django/stock/receptions-fournisseur/{r.id}/confirmer/', {}, format='json', **H)
        assert rr.status_code == 200, (rr.status_code, getattr(rr, 'data', None))
        p.refresh_from_db()
        return p

    def cherche(d, cle):
        if isinstance(d, dict):
            if cle in d:
                return d[cle]
            for v in d.values():
                x = cherche(v, cle)
                if x is not None:
                    return x
        return None

    def lire():
        v = api.get('/api/django/stock/produits/valorisation/', **H)
        a = api.get('/api/django/stock/produits/valorisation-a-date/', {'date': today.isoformat()}, **H)
        d = api.get('/api/django/reporting/dashboard/', **H)
        return {'valorisation_http': v.status_code, 'valorisation_total': str(v.data.get('total')),
                'valorisation_produits': sorted({l['sku'] for l in v.data.get('lignes', [])}),
                'a_date_http': a.status_code, 'a_date_total': str(a.data.get('total')),
                'a_date_produits': sorted(l['sku'] for l in a.data.get('lignes', [])),
                'dashboard_http': d.status_code,
                'dashboard_valeur_stock': cherche(d.data, 'valeur_stock') if d.status_code == 200 else str(d.data)[:100]}

    P = produit_recu('P', 40, '500', '800')
    R = produit_recu('R', 5, '200', '300')
    Q = produit_recu('Q', 10, '300', '450')
    obs = {'stock_recu': {'P': P.quantite_stock, 'R': R.quantite_stock, 'Q': Q.quantite_stock}}
    obs['avant'] = lire()
    rd = api.delete(f'/api/django/stock/produits/{P.id}/', **H)
    obs['delete_P'] = {'http': rd.status_code, 'archived': (rd.data or {}).get('archived') if rd.status_code == 200 else None,
                       'detail': str(getattr(rd, 'data', ''))[:160]}
    rp = api.patch(f'/api/django/stock/produits/{R.id}/', {'is_archived': True}, format='json', **H)
    obs['patch_R'] = {'http': rp.status_code, 'detail': None if rp.status_code < 400 else str(rp.data)[:160]}
    P.refresh_from_db()
    R.refresh_from_db()
    obs['apres_archives'] = {'P': {'is_archived': P.is_archived, 'quantite_stock': P.quantite_stock},
                             'R': {'is_archived': R.is_archived, 'quantite_stock': R.quantite_stock}}
    obs['apres'] = lire()
    print(obs)
    av, ap = obs['avant'], obs['apres']
    temoin_ok = (av['valorisation_total'] == av['a_date_total']
                 and Decimal(av['valorisation_total']) == Decimal('24000'))
    defaut = (P.is_archived and P.quantite_stock == 40
              and Decimal(ap['valorisation_total']) < Decimal(ap['a_date_total'])
              and 'S121-P' not in ap['valorisation_produits'] and 'S121-P' in ap['a_date_produits'])
    obs['ecart_meme_jour'] = str(Decimal(ap['a_date_total']) - Decimal(ap['valorisation_total']))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
