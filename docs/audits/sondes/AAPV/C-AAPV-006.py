# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K65 — DELETE d'un document d'achat FIGÉ : `ReceptionFournisseurViewSet` et `RetourFournisseurViewSet`
n'ont aucun `perform_destroy` (DocumentFigeMixin ne garde que update). Vraies routes, admin :
(A) BCF 10 × 100 HT, REC 10 confirmée (stock 10, reçu 10, provision 1 000) → DELETE receptions-fournisseur/<id>/ ;
(B) BCF 10 × 100 HT, REC 10 confirmée, retour 4 validé (stock 6, reçu 6) → DELETE retours-fournisseur/<id>/.
Attendu sain : 409 « confirmée / validé : annulez-le » ; probable : 204, effets (stock, reçu BCF, GR/IR)
laissés sans document, provision orpheline (reception NULL), aucun signal d'annulation."""
SONDE = {"constat": "C-AAPV-006", "sha": "5f603acce0",
         "attendu": "repro si DELETE reception confirmee -> 204 avec stock 10 / recu 10 / provision 1000 ouverte reception NULL ; DELETE retour valide -> 204 avec stock 6",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur", "stock.RetourFournisseur",
                     "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit,
                                   ReceptionFournisseur, RetourFournisseur, MouvementStock)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 006', slug='sonde-aapv-006')
    u = get_user_model().objects.create_user(username='sonde_aapv_006', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV6')
    url = '/api/django/stock/receptions-fournisseur/'

    def bcf_recu(tag):
        p = Produit.objects.create(company=co, nom=f'Onduleur AAPV6 {tag}', sku=f'AAPV-006-{tag}',
                                   prix_vente=Decimal('200'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-006-{tag}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('100'))
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        rc = api.post(f"{url}{r.data['id']}/confirmer/", {}, format='json', **H)
        return p, bc, lc, r.data['id'], rc.status_code

    # (A) réception confirmée supprimée
    p, bc, lc, rec_id, rc = bcf_recu('A')
    with TestCase.captureOnCommitCallbacks(execute=True) as rappels:
        rd = api.delete(f'{url}{rec_id}/', **H)
    p.refresh_from_db()
    lc.refresh_from_db()
    bc.refresh_from_db()
    A = {'confirmer': rc, 'delete_http': rd.status_code,
         'detail': None if rd.status_code < 400 else str(getattr(rd, 'data', ''))[:160],
         'reception_existe': ReceptionFournisseur.objects.filter(pk=rec_id).exists(),
         'stock': p.quantite_stock, 'mouvements_entree': MouvementStock.objects.filter(company=co, produit=p).count(),
         'bcf_recu': lc.quantite_recue, 'bcf_statut': bc.statut, 'rappels_on_commit': len(rappels),
         'gr_ir': [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
             company=co, bon_commande=bc).values('montant_provision', 'lettre', 'reception_id')]}
    # (B) retour validé supprimé
    p2, bc2, lc2, rec2, rc2 = bcf_recu('B')
    rr = api.post('/api/django/stock/retours-fournisseur/', {
        'fournisseur': f.id, 'bon_commande': bc2.id,
        'lignes': [{'produit': p2.id, 'quantite': 4, 'motif': 'defectueux'}]}, format='json', **H)
    rv = api.post(f"/api/django/stock/retours-fournisseur/{rr.data['id']}/valider/", {}, format='json', **H)
    rdel = api.delete(f"/api/django/stock/retours-fournisseur/{rr.data['id']}/", **H)
    p2.refresh_from_db()
    lc2.refresh_from_db()
    B = {'retour_valider': rv.status_code, 'delete_http': rdel.status_code,
         'detail': None if rdel.status_code < 400 else str(getattr(rdel, 'data', ''))[:160],
         'retour_existe': RetourFournisseur.objects.filter(pk=rr.data['id']).exists(),
         'stock': p2.quantite_stock, 'bcf_recu': lc2.quantite_recue,
         'mouvements_retour_orphelins': MouvementStock.objects.filter(company=co, produit=p2,
                                                                      reference=rr.data['reference']).count()}
    obs = {'A_reception_confirmee': A, 'B_retour_valide': B}
    print(obs)
    temoin_ok = rc == 200 and rc2 == 200 and rv.status_code == 200
    defaut_a = (rd.status_code == 204 and not A['reception_existe'] and A['stock'] == 10 and A['bcf_recu'] == 10
                and A['gr_ir'] == [{'montant_provision': '1000.00', 'lettre': 'False', 'reception_id': 'None'}])
    defaut_b = rdel.status_code == 204 and not B['retour_existe'] and B['stock'] == 6
    obs.update({'temoin_ok': temoin_ok, 'defaut_A': defaut_a, 'defaut_B': defaut_b})
    obs['repro'] = bool(temoin_ok and (defaut_a or defaut_b))
    return obs
