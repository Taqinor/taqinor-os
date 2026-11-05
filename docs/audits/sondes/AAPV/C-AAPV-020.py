# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K21 — « Annuler » un brouillon sans verrou ni relecture écrase une confirmation / validation concurrente.
Interleaving rejoué SÉQUENTIELLEMENT (jamais de threads) : (1) l'action `annuler` lit l'instance BROUILLON
(`get_object`, hors verrou) ; (2) une autre requête confirme la réception (vraie route `confirmer/`) et commite ;
(3) l'action `annuler` reprend sur l'instance PÉRIMÉE : branche « brouillon » = `statut=ANNULE; save(update_fields)`.
L'étape (1)/(3) est jouée par la VRAIE route `annuler/` dont `get_object` rend l'instance lue en (1)
(ce qu'il aurait rendu avant le commit de (2)). Idem retour fournisseur (`valider/` puis `annuler/` périmé).
Témoin T : même réception confirmée, `annuler/` sur instance FRAÎCHE → contre-passation (stock rendu)."""
SONDE = {"constat": "C-AAPV-020", "sha": "b432084786",
         "attendu": "repro si R : annuler 200 sur instance périmée -> réception « annule » avec ENTREE 10 en stock, provision GR/IR ouverte, facturer refusé ; RF : retour « annule » avec SORTIE déjà posée",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.BonCommandeFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, ReceptionFournisseur, MouvementStock)
    from apps.achats.models import RetourFournisseur
    from apps.stock.views.reception_fournisseur import ReceptionFournisseurViewSet
    from apps.stock.views.retour_fournisseur import RetourFournisseurViewSet
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 020', slug='sonde-aapv-020')
    u = get_user_model().objects.create_user(username='sonde_aapv_020', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV20')
    url = '/api/django/stock/receptions-fournisseur/'

    def bcf(n):
        p = Produit.objects.create(company=co, nom=f'Onduleur AAPV20-{n}', sku=f'AAPV-020-{n}',
                                   prix_vente=Decimal('200'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-020-{n}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('100'))
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        return p, bc, lc, r.data['id']

    def etat(p, rec_id):
        p.refresh_from_db()
        rec = ReceptionFournisseur.objects.get(pk=rec_id)
        provs = list(ReceptionNonFacturee.objects.filter(company=co, reception_id=rec_id).values_list(
            'montant_provision', 'lettre'))
        mvts = list(MouvementStock.objects.filter(company=co, produit=p).order_by('id').values_list(
            'type_mouvement', 'quantite', 'reference'))
        return {'statut': rec.statut, 'stock': p.quantite_stock,
                'provisions': [(str(m), l) for m, l in provs], 'mouvements': mvts}

    obs = {}
    # R — interleaving « annuler (lecture brouillon) / confirmer (commit) / annuler (écriture) »
    p, bc, lc, rec_id = bcf('R')
    perimee = ReceptionFournisseur.objects.get(pk=rec_id)          # (1) get_object de la requête « annuler »
    rc = api.post(f'{url}{rec_id}/confirmer/', {}, format='json', **H)   # (2) autre requête : confirmer
    with mock.patch.object(ReceptionFournisseurViewSet, 'get_object', return_value=perimee):
        with TestCase.captureOnCommitCallbacks(execute=True):
            ra = api.post(f'{url}{rec_id}/annuler/', {}, format='json', **H)  # (3) suite de « annuler »
    lc.refresh_from_db()
    bc.refresh_from_db()
    rf = api.post(f'{url}{rec_id}/facturer/', {}, format='json', **H)
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra2 = api.post(f'{url}{rec_id}/annuler/', {}, format='json', **H)
    obs['R'] = {'confirmer': rc.status_code, 'annuler_perime': ra.status_code, **etat(p, rec_id),
                'bcf_recu': lc.quantite_recue, 'bcf_statut': bc.statut,
                'facturer_ensuite': rf.status_code, 'facturer_detail': str(getattr(rf, 'data', ''))[:140],
                'annuler_ensuite': ra2.status_code, 'etat_apres_annuler_ensuite': etat(p, rec_id)}
    # T — témoin : même geste, instance fraîche (la branche confirmée contre-passe)
    pT, bcT, lcT, recT = bcf('T')
    api.post(f'{url}{recT}/confirmer/', {}, format='json', **H)
    with TestCase.captureOnCommitCallbacks(execute=True):
        raT = api.post(f'{url}{recT}/annuler/', {}, format='json', **H)
    obs['T'] = {'annuler_frais': raT.status_code, **etat(pT, recT)}
    # RF — retour fournisseur : « annuler » lit le brouillon, « valider » commite, « annuler » écrit
    pR, bcR, lcR, recR = bcf('RF')
    api.post(f'{url}{recR}/confirmer/', {}, format='json', **H)
    urlr = '/api/django/stock/retours-fournisseur/'
    rr = api.post(urlr, {'fournisseur': f.id, 'bon_commande': bcR.id,
                         'lignes': [{'produit': pR.id, 'quantite': 4, 'motif': 'défectueux'}]}, format='json', **H)
    ret_id = rr.data['id']
    ret_perime = RetourFournisseur.objects.get(pk=ret_id)
    rv = api.post(f'{urlr}{ret_id}/valider/', {}, format='json', **H)
    with mock.patch.object(RetourFournisseurViewSet, 'get_object', return_value=ret_perime):
        rann = api.post(f'{urlr}{ret_id}/annuler/', {}, format='json', **H)
    pR.refresh_from_db()
    lcR.refresh_from_db()
    rav = api.post(f'{urlr}{ret_id}/generer-avoir/', {}, format='json', **H)
    obs['RF'] = {'creation': rr.status_code, 'valider': rv.status_code, 'annuler_perime': rann.status_code,
                 'statut_retour': RetourFournisseur.objects.get(pk=ret_id).statut, 'stock': pR.quantite_stock,
                 'bcf_recu': lcR.quantite_recue,
                 'sorties_retour': list(MouvementStock.objects.filter(company=co, produit=pR,
                                                                      type_mouvement='sortie').values_list('quantite', flat=True)),
                 'generer_avoir_ensuite': rav.status_code, 'avoir_detail': str(getattr(rav, 'data', ''))[:140]}
    print(obs)
    r, t, x = obs['R'], obs['T'], obs['RF']
    temoin_ok = t['annuler_frais'] == 200 and t['statut'] == 'annule' and t['stock'] == 0
    defaut_r = (r['confirmer'] == 200 and r['annuler_perime'] == 200 and r['statut'] == 'annule'
                and r['stock'] == 10)
    defaut_rf = (x['valider'] == 200 and x['annuler_perime'] == 200 and x['statut_retour'] == 'annule'
                 and x['stock'] == 6)
    obs['temoin_ok'] = temoin_ok
    obs['repro_reception'] = defaut_r
    obs['repro_retour'] = defaut_rf
    obs['repro'] = bool(temoin_ok and defaut_r and defaut_rf)
    return obs
