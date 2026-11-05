# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K24 — le retour fournisseur laisse le lot et les séries « en stock ».
(R) réception de 10 batteries lot L-0425 + séries SN1..SN10 par la vraie route `recevoir/` ; retour de 3
(`retours-fournisseur/` + `valider/`, seul corps possible : produit, quantité, motif) → stock 7 ; lit
LotEntrepot.quantite_restante et le compte SerieEntrepot « en stock ».
(T) témoin jumeau : même réception sur un autre BCF puis `receptions-fournisseur/<id>/annuler/` → le lot est
débité et les séries passent « retourné » (ASTK57, rappels on_commit exécutés)."""
SONDE = {"constat": "C-AAPV-022", "sha": "b432084786",
         "attendu": "repro si R : stock 7 mais lot L-0425 restant 10 et 10 séries en_stock ; T : lot 0, 0 série en_stock",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.LotEntrepot", "installations.SerieEntrepot"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, ReceptionFournisseur, LotEntrepot)
    from apps.installations.models_serie_entrepot import SerieEntrepot
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 022', slug='sonde-aapv-022')
    u = get_user_model().objects.create_user(username='sonde_aapv_022', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV22')
    urlb = '/api/django/stock/bons-commande-fournisseur/'
    urlr = '/api/django/stock/retours-fournisseur/'

    def recevoir(n):
        p = Produit.objects.create(company=co, nom=f'Batterie AAPV22-{n}', sku=f'AAPV-022-{n}',
                                   prix_vente=Decimal('3000'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-022-{n}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('2000'))
        series = [f'{n}-SN{i}' for i in range(1, 11)]
        r = api.post(f'{urlb}{bc.id}/recevoir/', {'receptions': [{'ligne': lc.id, 'quantite': 10,
                                                                   'numeros_serie': series,
                                                                   'numero_lot': f'L-0425-{n}'}]},
                     format='json', **H)
        return p, bc, r.status_code

    def etat(p):
        p.refresh_from_db()
        lots = list(LotEntrepot.objects.filter(company=co, produit=p).values_list('numero_lot', 'quantite_restante'))
        en_stock = SerieEntrepot.objects.filter(company=co, produit=p, statut=SerieEntrepot.Statut.EN_STOCK).count()
        return {'stock': p.quantite_stock, 'lots': lots, 'series_en_stock': en_stock,
                'series_statuts': sorted(set(SerieEntrepot.objects.filter(company=co, produit=p).values_list(
                    'statut', flat=True)))}

    obs = {}
    p, bc, rc = recevoir('R')
    avant = etat(p)
    rr = api.post(urlr, {'fournisseur': f.id, 'bon_commande': bc.id,
                         'lignes': [{'produit': p.id, 'quantite': 3, 'motif': 'SN3, SN7, SN9 défectueuses'}]},
                  format='json', **H)
    rv = api.post(f'{urlr}{rr.data["id"]}/valider/', {}, format='json', **H)
    fefo = api.get(f'/api/django/stock/lots-entrepot/fefo/?produit={p.id}&quantite=10', **H)
    obs['R'] = {'recevoir': rc, 'avant_retour': avant, 'retour_creation': rr.status_code,
                'retour_valider': rv.status_code, 'apres_retour': etat(p),
                'fefo_http': fefo.status_code, 'fefo': str(getattr(fefo, 'data', ''))[:200]}
    pT, bcT, rcT = recevoir('T')
    recT = ReceptionFournisseur.objects.filter(bon_commande=bcT).first()
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra = api.post(f'/api/django/stock/receptions-fournisseur/{recT.id}/annuler/', {}, format='json', **H)
    obs['T'] = {'recevoir': rcT, 'annuler': ra.status_code, 'apres_annulation': etat(pT)}
    print(obs)
    r, t = obs['R'], obs['T']
    temoin_ok = (t['annuler'] == 200 and t['apres_annulation']['stock'] == 0
                 and t['apres_annulation']['series_en_stock'] == 0
                 and all(q == 0 for _, q in t['apres_annulation']['lots']))
    defaut = (r['retour_valider'] == 200 and r['apres_retour']['stock'] == 7
              and r['apres_retour']['series_en_stock'] == 10
              and any(q == 10 for _, q in r['apres_retour']['lots']))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
