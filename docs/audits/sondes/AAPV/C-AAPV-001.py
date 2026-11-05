# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K20 — annuler une réception CONFIRMÉE dont une partie a déjà été consommée : la sortie de stock est
plafonnée au stock en main (XSTK8) mais la ligne de BCF, la provision GR/IR (abonné ASTK57) et l'événement
défont la quantité ENTIÈRE. Chaîne : BCF 10 × 100 HT envoyé, REC confirmée 10 (vraie route), SORTIE 7
(consommation), POST receptions-fournisseur/<id>/annuler/ (vraie route, rappels on_commit exécutés).
Attendu sain : refus (unités consommées) OU annulation au prorata (BCF reçu 7, provision 700)."""
SONDE = {"constat": "C-AAPV-001", "sha": "5f603acce0",
         "attendu": "repro si annulation 200 avec sortie 3 mais quantite_recue BCF 0 et provision GR/IR supprimee (700 de dette perdue)",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.BonCommandeFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, ReceptionFournisseur, MouvementStock)
    from apps.stock.services import record_stock_movement
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 001', slug='sonde-aapv-001')
    u = get_user_model().objects.create_user(username='sonde_aapv_001', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Panneau AAPV1', sku='AAPV-001', prix_vente=Decimal('200'),
                               quantite_stock=0)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV1')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-001',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('100'))
    url = '/api/django/stock/receptions-fournisseur/'
    r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                 format='json', **H)
    rec_id = r.data['id']
    rc = api.post(f'{url}{rec_id}/confirmer/', {}, format='json', **H)
    p.refresh_from_db()
    lc.refresh_from_db()
    prov = ReceptionNonFacturee.objects.filter(company=co, reception_id=rec_id).first()
    obs = {'creation': r.status_code, 'confirmer': rc.status_code, 'stock_apres_conf': p.quantite_stock,
           'recu_apres_conf': lc.quantite_recue,
           'provision_apres_conf': None if prov is None else str(prov.montant_provision)}
    # consommation de 7 (sortie chantier/vente quelconque)
    p = Produit.objects.get(pk=p.pk)
    record_stock_movement(company=co, produit=p, type_mouvement=MouvementStock.TypeMouvement.SORTIE, quantite=7,
                          quantite_avant=p.quantite_stock, quantite_apres=p.quantite_stock - 7,
                          reference='CONSO-AAPV1', note='consommation sonde', created_by=u)
    p.refresh_from_db()
    obs['stock_apres_conso'] = p.quantite_stock
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra = api.post(f'{url}{rec_id}/annuler/', {}, format='json', **H)
    p.refresh_from_db()
    lc.refresh_from_db()
    bc.refresh_from_db()
    sortie_annul = list(MouvementStock.objects.filter(company=co, reference__startswith='ANNUL-').values_list(
        'quantite', flat=True))
    provs = list(ReceptionNonFacturee.objects.filter(company=co, bon_commande=bc).values(
        'montant_provision', 'lettre', 'reception_id'))
    obs.update({'annuler_http': ra.status_code,
                'detail': None if ra.status_code < 400 else str(ra.data)[:160],
                'sortie_annul': sortie_annul, 'stock_final': p.quantite_stock,
                'bcf_quantite_recue': lc.quantite_recue, 'bcf_reste_du': lc.quantite - lc.quantite_recue,
                'bcf_statut': bc.statut,
                'provisions_gr_ir': [{k: str(v) for k, v in d.items()} for d in provs]})
    print(obs)
    temoin_ok = (obs['confirmer'] == 200 and obs['stock_apres_conf'] == 10 and obs['provision_apres_conf'] == '1000.00'
                 and obs['stock_apres_conso'] == 3)
    defaut = (ra.status_code == 200 and lc.quantite_recue == 0 and not provs)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
