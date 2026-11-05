# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K46 — le lettrage GR/IR au cumul (`lettrer_gr_ir_facture`, ASTK125) est FIFO sur les provisions du BCF,
quelle que soit la réception facturée ; l'extourne d'annulation (`extourner_gr_ir_reception`) ne supprime
que `lettre=False`. Vraies routes : BCF 20 × 100 HT, R1 10 et R2 10 confirmées (P1, P2 = 1 000), « Facturer »
R2 (F2 1 000 HT, FK reception=R2), annuler R1 (autorisé : R1 n'est pas facturée).
Attendu sain : GR/IR ouvert du BCF = 0 (R2 reçue ET facturée, R1 annulée) ; probable : P1 lettrée par F2 et
restée sur R1 annulée, P2 ouverte 1 000."""
SONDE = {"constat": "C-AAPV-004", "sha": "5f603acce0",
         "attendu": "repro si apres annulation de R1 : P1 lettree (facture F2, reception R1 annulee) et P2 ouverte 1000 -> GR/IR ouvert 1000 au lieu de 0",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.FactureFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit,
                                   ReceptionFournisseur)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 004', slug='sonde-aapv-004')
    u = get_user_model().objects.create_user(username='sonde_aapv_004', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Structure AAPV4', sku='AAPV-004', prix_vente=Decimal('200'),
                               quantite_stock=0)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV4')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-004',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=20,
                                                    prix_achat_unitaire=Decimal('100'))
    url = '/api/django/stock/receptions-fournisseur/'
    ids = []
    for _ in range(2):
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        ids.append(r.data['id'])
        api.post(f"{url}{r.data['id']}/confirmer/", {}, format='json', **H)
    r1, r2 = ids

    def gr_ir():
        return [{'reception': ('R1' if d['reception_id'] == r1 else 'R2' if d['reception_id'] == r2 else d['reception_id']),
                 'montant': str(d['montant_provision']), 'lettre': d['lettre'], 'facture_id': d['facture_id']}
                for d in ReceptionNonFacturee.objects.filter(company=co, bon_commande=bc).order_by('pk').values(
                    'reception_id', 'montant_provision', 'lettre', 'facture_id')]
    obs = {'gr_ir_apres_receptions': gr_ir()}
    rf = api.post(f'{url}{r2}/facturer/', {}, format='json', **H)
    obs['facturer_R2'] = rf.status_code
    f2 = rf.data.get('id')
    obs['f2_ht'] = rf.data.get('montant_ht')
    obs['gr_ir_apres_facture_R2'] = gr_ir()
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra = api.post(f'{url}{r1}/annuler/', {}, format='json', **H)
    obs['annuler_R1'] = ra.status_code
    obs['statuts'] = {'R1': ReceptionFournisseur.objects.get(pk=r1).statut,
                      'R2': ReceptionFournisseur.objects.get(pk=r2).statut}
    obs['gr_ir_final'] = gr_ir()
    ouvert = sum(Decimal(d['montant']) for d in obs['gr_ir_final'] if not d['lettre'])
    lettre_sur_annulee = [d for d in obs['gr_ir_final'] if d['lettre'] and d['reception'] == 'R1']
    obs['gr_ir_ouvert'] = str(ouvert)
    obs['provision_lettree_sur_R1_annulee'] = bool(lettre_sur_annulee)
    print(obs)
    temoin_ok = (len(obs['gr_ir_apres_receptions']) == 2 and rf.status_code == 201 and ra.status_code == 200)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and ouvert == Decimal('1000.00') and lettre_sur_annulee
                        and lettre_sur_annulee[0]['facture_id'] == f2)
    return obs
