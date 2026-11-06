# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K22 — un retour fournisseur VALIDÉ (apply_retour_fournisseur) ne touche pas la provision GR/IR : la dette
latente reste à la quantité reçue brute, et la facture du fournisseur pour le NET gardé ne la lettre jamais
(lettrage au cumul, ASTK125). Chaîne par les vraies routes : BCF 10 × 100 HT, REC 10 confirmée (provision
1 000), retour RF de 4 lié au BCF validé, facture fournisseur 600 HT saisie puis liée au BCF par PATCH (OCR).
Attendu sain : provision ramenée à 600 au retour puis lettrée par la facture 600 (GR/IR ouvert 0)."""
SONDE = {"constat": "C-AAPV-002", "sha": "5f603acce0",
         "attendu": "repro si apres retour 4 + facture 600 HT liee : provision 1000 toujours ouverte (lettre=False), GR/IR ouvert 1000 au lieu de 0",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur", "stock.RetourFournisseur",
                     "stock.FactureFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 002', slug='sonde-aapv-002')
    u = get_user_model().objects.create_user(username='sonde_aapv_002', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Onduleur AAPV2', sku='AAPV-002', prix_vente=Decimal('200'),
                               quantite_stock=0)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV2')
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-002',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('100'))
    url = '/api/django/stock/receptions-fournisseur/'
    r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                 format='json', **H)
    rec_id = r.data['id']
    rc = api.post(f'{url}{rec_id}/confirmer/', {}, format='json', **H)

    def gr_ir():
        return [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
            company=co, bon_commande=bc).values('montant_provision', 'lettre', 'facture_id')]
    obs = {'confirmer': rc.status_code, 'gr_ir_apres_reception': gr_ir()}
    rr = api.post('/api/django/stock/retours-fournisseur/', {
        'fournisseur': f.id, 'bon_commande': bc.id,
        'lignes': [{'produit': p.id, 'quantite': 4, 'motif': 'defectueux'}]}, format='json', **H)
    obs['retour_creation'] = rr.status_code
    if rr.status_code != 201:
        obs['retour_detail'] = str(rr.data)[:200]
        print(obs)
        return obs
    rv = api.post(f"/api/django/stock/retours-fournisseur/{rr.data['id']}/valider/", {}, format='json', **H)
    p.refresh_from_db()
    lc.refresh_from_db()
    obs.update({'retour_valider': rv.status_code, 'stock_apres_retour': p.quantite_stock,
                'bcf_recu_apres_retour': lc.quantite_recue, 'gr_ir_apres_retour': gr_ir()})
    # facture du fournisseur pour les 6 gardes : saisie puis liee au BCF (chemin OCR / PATCH, ASTK99)
    rf = api.post('/api/django/stock/factures-fournisseur/', {
        'fournisseur': f.id, 'ref_fournisseur': 'FAC-F2-600', 'date_facture': timezone.now().date().isoformat(),
        'montant_ht': '600.00', 'montant_tva': '120.00', 'montant_ttc': '720.00'}, format='json', **H)
    obs['facture_creation'] = rf.status_code
    if rf.status_code != 201:
        obs['facture_detail'] = str(rf.data)[:200]
        print(obs)
        return obs
    rp = api.patch(f"/api/django/stock/factures-fournisseur/{rf.data['id']}/", {'bon_commande': bc.id},
                   format='json', **H)
    obs.update({'facture_lien_bcf': rp.status_code,
                'facture_statut_controle': rp.data.get('statut_controle') if rp.status_code == 200 else str(rp.data)[:160],
                'gr_ir_final': gr_ir()})
    ouvert = sum(Decimal(d['montant_provision']) for d in obs['gr_ir_final'] if d['lettre'] == 'False')
    obs['gr_ir_ouvert'] = str(ouvert)
    print(obs)
    temoin_ok = (rc.status_code == 200 and obs['gr_ir_apres_reception'] == [
        {'montant_provision': '1000.00', 'lettre': 'False', 'facture_id': 'None'}]
                 and rv.status_code == 200 and obs['stock_apres_retour'] == 6 and rp.status_code == 200)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and ouvert == Decimal('1000.00'))
    return obs
