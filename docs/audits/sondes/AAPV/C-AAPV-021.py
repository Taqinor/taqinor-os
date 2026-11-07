# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K23 — retour fournisseur sur un BCF lié à un chantier.
(A) BCF `chantier_livraison` (livraison directe, XPUR23) : stock libre 5, réception 10 par la vraie route
`bons-commande-fournisseur/<id>/recevoir/` (entrée 10 + sortie directe 10), puis l'annulation est refusée
(« passer par un retour », ASTK54 — témoin) ; retour 2 par `retours-fournisseur/` + `valider/` : sort-il du
stock LIBRE 2 unités qui n'y sont jamais entrées ?
(B) BCF `chantier_origine` (YPROC10) : réception 10 → réservation chantier 10 ; retour 4 validé : la
réservation est-elle replafonnée au reçu net (6), comme le fait l'annulation (ASTK57) ?"""
SONDE = {"constat": "C-AAPV-021", "sha": "b432084786",
         "attendu": "repro si A : retour 200 et stock libre 5 -> 3 ; B : stock 6 mais réservation chantier toujours 10",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "installations.StockReservation", "installations.Installation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, StockReservation
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, ReceptionFournisseur, MouvementStock)
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 021', slug='sonde-aapv-021')
    u = get_user_model().objects.create_user(username='sonde_aapv_021', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client AAPV21', prenom='T')
    f = Fournisseur.objects.create(company=co, nom='F-AAPV21')
    urlb = '/api/django/stock/bons-commande-fournisseur/'
    urlr = '/api/django/stock/retours-fournisseur/'
    obs = {}

    def retour(bc, p, q):
        rr = api.post(urlr, {'fournisseur': f.id, 'bon_commande': bc.id,
                             'lignes': [{'produit': p.id, 'quantite': q, 'motif': 'défectueux'}]},
                      format='json', **H)
        rv = api.post(f'{urlr}{rr.data["id"]}/valider/', {}, format='json', **H)
        return rr.status_code, rv.status_code, (None if rv.status_code < 400 else str(rv.data)[:160])

    # (A) livraison directe chantier
    chA = Installation.objects.create(company=co, reference='CH-AAPV21-A', client=cl)
    pA = Produit.objects.create(company=co, nom='Onduleur AAPV21-A', sku='AAPV-021-A', prix_vente=Decimal('1500'),
                                quantite_stock=5)
    bcA = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-021-A',
                                                chantier_livraison=chA, statut=BonCommandeFournisseur.Statut.ENVOYE)
    lcA = LigneBonCommandeFournisseur.objects.create(bon_commande=bcA, produit=pA, quantite=10,
                                                     prix_achat_unitaire=Decimal('1000'))
    rcv = api.post(f'{urlb}{bcA.id}/recevoir/', {'receptions': [{'ligne': lcA.id, 'quantite': 10}]},
                   format='json', **H)
    pA.refresh_from_db()
    stock_apres_recep = pA.quantite_stock
    recA = ReceptionFournisseur.objects.filter(bon_commande=bcA).first()
    with TestCase.captureOnCommitCallbacks(execute=True):
        rann = api.post(f'/api/django/stock/receptions-fournisseur/{recA.id}/annuler/', {}, format='json', **H)
    c, v, d = retour(bcA, pA, 2)
    pA.refresh_from_db()
    lcA.refresh_from_db()
    obs['A'] = {'recevoir': rcv.status_code, 'stock_libre_apres_reception': stock_apres_recep,
                'annuler_reception': rann.status_code, 'annuler_detail': str(getattr(rann, 'data', ''))[:120],
                'retour_creation': c, 'retour_valider': v, 'retour_detail': d,
                'stock_libre_final': pA.quantite_stock, 'bcf_recu': lcA.quantite_recue,
                'mouvements': list(MouvementStock.objects.filter(company=co, produit=pA).order_by('id').values_list(
                    'type_mouvement', 'quantite', 'reference'))}
    # (B) besoin chantier (chantier_origine) : réservation YPROC10
    chB = Installation.objects.create(company=co, reference='CH-AAPV21-B', client=cl)
    pB = Produit.objects.create(company=co, nom='Batterie AAPV21-B', sku='AAPV-021-B', prix_vente=Decimal('3000'),
                                quantite_stock=0)
    bcB = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-021-B',
                                                chantier_origine=chB, statut=BonCommandeFournisseur.Statut.ENVOYE)
    lcB = LigneBonCommandeFournisseur.objects.create(bon_commande=bcB, produit=pB, quantite=10,
                                                     prix_achat_unitaire=Decimal('2000'))
    rcvB = api.post(f'{urlb}{bcB.id}/recevoir/', {'receptions': [{'ligne': lcB.id, 'quantite': 10}]},
                    format='json', **H)
    resa = StockReservation.objects.filter(installation=chB, produit=pB).first()
    resa_avant = None if resa is None else (resa.quantite, resa.active, resa.consomme)
    cB, vB, dB = retour(bcB, pB, 4)
    pB.refresh_from_db()
    lcB.refresh_from_db()
    resa = StockReservation.objects.filter(installation=chB, produit=pB).first()
    obs['B'] = {'recevoir': rcvB.status_code, 'reservation_apres_reception': resa_avant,
                'retour_valider': vB, 'retour_detail': dB, 'stock': pB.quantite_stock, 'bcf_recu': lcB.quantite_recue,
                'reservation_apres_retour': None if resa is None else (resa.quantite, resa.active, resa.consomme)}
    print(obs)
    a, b = obs['A'], obs['B']
    temoin_ok = (a['recevoir'] == 200 and a['stock_libre_apres_reception'] == 5 and a['annuler_reception'] == 400
                 and b['recevoir'] == 200 and b['reservation_apres_reception'] is not None
                 and b['reservation_apres_reception'][0] == 10)
    defaut_a = a['retour_valider'] == 200 and a['stock_libre_final'] == 3
    defaut_b = (b['retour_valider'] == 200 and b['stock'] == 6 and b['reservation_apres_retour'] is not None
                and b['reservation_apres_retour'][0] == 10 and b['reservation_apres_retour'][1])
    obs['temoin_ok'] = temoin_ok
    obs['repro_A'] = defaut_a
    obs['repro_B'] = defaut_b
    obs['repro'] = bool(temoin_ok and (defaut_a or defaut_b))
    return obs
