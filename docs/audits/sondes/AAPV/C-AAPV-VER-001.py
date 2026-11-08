# flake8: noqa  (sonde de contre-visite « vérifie AAPV », rejouable par scripts/sonde.py — METHODE §C.4)
"""Contre-visite AAPV9 — la facture arrive AVANT le retour. BCF 10 × 100 HT, REC 10 confirmée (provision 1 000),
facture fournisseur 600 HT saisie puis liée au BCF par PATCH (ASTK125 : 600 < 1 000, la provision reste ouverte),
puis retour de 4 validé : `reduire_gr_ir_retour` ramène la provision à 600 mais ne relance pas le lettrage.
Attendu sain : provision 600 lettrée par la facture 600 (GR/IR ouvert 0). Ordre inverse (retour puis facture) =
C-AAPV-002, fermé par AAPV9."""
SONDE = {"constat": "C-AAPV-VER-001", "sha": "76344a269d",
         "attendu": "repro si facture 600 liee puis retour 4 valide : provision 600 ouverte (lettre=False), GR/IR ouvert 600 au lieu de 0",
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
    co = Company.objects.create(nom='Sonde AAPV VER 001', slug='sonde-aapv-ver-001')
    u = get_user_model().objects.create_user(username='sonde_aapv_ver_001', password='x', role_legacy='admin',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur VER1', sku='AAPV-VER-001', prix_vente=Decimal('200'),
                               quantite_stock=0)
    f = Fournisseur.objects.create(company=co, nom='F-VER1')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-VER-001',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('100'))

    def gr_ir():
        return [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
            company=co, bon_commande=bc).values('montant_provision', 'lettre', 'facture_id')]

    url = '/api/django/stock/receptions-fournisseur/'
    with TestCase.captureOnCommitCallbacks(execute=True):
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        rc = api.post(f"{url}{r.data['id']}/confirmer/", {}, format='json', **H)
    obs = {'confirmer': rc.status_code, 'gr_ir_apres_reception': gr_ir()}
    with TestCase.captureOnCommitCallbacks(execute=True):
        rf = api.post('/api/django/stock/factures-fournisseur/', {
            'fournisseur': f.id, 'ref_fournisseur': 'FAC-VER1-600', 'date_facture': timezone.now().date().isoformat(),
            'montant_ht': '600.00', 'montant_tva': '120.00', 'montant_ttc': '720.00'}, format='json', **H)
        rp = api.patch(f"/api/django/stock/factures-fournisseur/{rf.data['id']}/", {'bon_commande': bc.id},
                       format='json', **H) if rf.status_code == 201 else None
    obs.update({'facture_creation': rf.status_code, 'facture_lien_bcf': getattr(rp, 'status_code', None),
                'gr_ir_apres_facture': gr_ir()})
    with TestCase.captureOnCommitCallbacks(execute=True):
        rr = api.post('/api/django/stock/retours-fournisseur/', {
            'fournisseur': f.id, 'bon_commande': bc.id,
            'lignes': [{'produit': p.id, 'quantite': 4, 'motif': 'defectueux'}]}, format='json', **H)
        rv = api.post(f"/api/django/stock/retours-fournisseur/{rr.data['id']}/valider/", {}, format='json',
                      **H) if rr.status_code == 201 else None
    obs.update({'retour_creation': rr.status_code, 'retour_valider': getattr(rv, 'status_code', None),
                'gr_ir_final': gr_ir()})
    ouvert = sum(Decimal(d['montant_provision']) for d in obs['gr_ir_final'] if d['lettre'] == 'False')
    obs['gr_ir_ouvert'] = str(ouvert)
    print(obs)
    temoin_ok = (rc.status_code == 200 and getattr(rp, 'status_code', None) == 200
                 and obs['gr_ir_apres_facture'] == [{'montant_provision': '1000.00', 'lettre': 'False',
                                                     'facture_id': 'None'}]
                 and getattr(rv, 'status_code', None) == 200)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and ouvert == Decimal('600.00'))
    return obs
