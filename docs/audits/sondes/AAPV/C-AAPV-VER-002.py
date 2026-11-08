# flake8: noqa  (sonde de contre-visite « vérifie AAPV », rejouable par scripts/sonde.py — METHODE §C.4)
"""Contre-visite AAPV9/AAPV43 — dé-lettrage après retour. BCF 10 × 100 HT, REC 10 confirmée, « Facturer » la
réception (1 000 HT, provision lettrée), retour de 4 validé (`reduire_gr_ir_retour` ne touche pas une provision
lettrée), DELETE de la facture pour refacturer au net (`delettrer_gr_ir_facture` rouvre la provision à 1 000),
puis facture 600 HT liée au BCF par PATCH : 600 < 1 000, la provision n'est jamais lettrée.
Attendu sain : provision rouverte au reçu net valorisé (600) puis lettrée par la facture 600 (GR/IR ouvert 0)."""
SONDE = {"constat": "C-AAPV-VER-002", "sha": "76344a269d",
         "attendu": "repro si apres facturer + retour 4 + suppression de la facture + facture 600 liee : GR/IR ouvert 1000 au lieu de 0",
         "modeles": ["stock.Produit", "stock.ReceptionFournisseur", "stock.RetourFournisseur",
                     "stock.FactureFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV VER 002', slug='sonde-aapv-ver-002')
    u = get_user_model().objects.create_user(username='sonde_aapv_ver_002', password='x', role_legacy='admin',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur VER2', sku='AAPV-VER-002', prix_vente=Decimal('200'),
                               quantite_stock=0)
    f = Fournisseur.objects.create(company=co, nom='F-VER2')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-VER-002',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('100'))

    def gr_ir():
        return [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
            company=co, bon_commande=bc).values('montant_provision', 'lettre')]

    url = '/api/django/stock/receptions-fournisseur/'
    with TestCase.captureOnCommitCallbacks(execute=True):
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        rec_id = r.data['id']
        rc = api.post(f'{url}{rec_id}/confirmer/', {}, format='json', **H)
    with TestCase.captureOnCommitCallbacks(execute=True):
        rfa = api.post(f'{url}{rec_id}/facturer/', {}, format='json', **H)
    obs = {'confirmer': rc.status_code, 'facturer': rfa.status_code, 'gr_ir_apres_facturer': gr_ir()}
    with TestCase.captureOnCommitCallbacks(execute=True):
        rr = api.post('/api/django/stock/retours-fournisseur/', {
            'fournisseur': f.id, 'bon_commande': bc.id,
            'lignes': [{'produit': p.id, 'quantite': 4, 'motif': 'defectueux'}]}, format='json', **H)
        rv = api.post(f"/api/django/stock/retours-fournisseur/{rr.data['id']}/valider/", {}, format='json',
                      **H) if rr.status_code == 201 else None
    obs.update({'retour_valider': getattr(rv, 'status_code', None), 'gr_ir_apres_retour': gr_ir()})
    with TestCase.captureOnCommitCallbacks(execute=True):
        rd = api.delete(f"/api/django/stock/factures-fournisseur/{rfa.data['id']}/", **H) \
            if rfa.status_code == 201 else None
    obs.update({'suppression_facture': getattr(rd, 'status_code', None), 'gr_ir_apres_suppression': gr_ir()})
    with TestCase.captureOnCommitCallbacks(execute=True):
        rf = api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': f.id, 'ref_fournisseur': 'FAC-VER2-600', 'date_facture': timezone.now().date().isoformat(),
            'montant_ht': '600.00', 'montant_tva': '120.00', 'montant_ttc': '720.00'}, format='json', **H)
        rp = api.patch(f"/api/django/stock/factures-fournisseur/{rf.data['id']}/", {'bon_commande': bc.id},
                       format='json', **H) if rf.status_code == 201 else None
    obs.update({'facture_lien_bcf': getattr(rp, 'status_code', None), 'gr_ir_final': gr_ir()})
    ouvert = sum(Decimal(d['montant_provision']) for d in obs['gr_ir_final'] if d['lettre'] == 'False')
    obs['gr_ir_ouvert'] = str(ouvert)
    print(obs)
    temoin_ok = (rc.status_code == 200 and rfa.status_code == 201
                 and obs['gr_ir_apres_facturer'] == [{'montant_provision': '1000.00', 'lettre': 'True'}]
                 and getattr(rv, 'status_code', None) == 200 and getattr(rd, 'status_code', None) == 204
                 and getattr(rp, 'status_code', None) == 200)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and ouvert == Decimal('1000.00'))
    return obs
