# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K45 — la garde ERR-ASTK54 d'annulation (`factures_ouvertes_de_reception`) ne voit que la FK `reception` ou
la note « Facture réception <REF> ». Une facture fournisseur saisie puis liée au BCF par PATCH (chemin OCR /
ASTK99) n'a ni l'une ni l'autre : la réception qu'elle facture s'annule quand même. Vraies routes :
BCF 10 × 1 000 HT, REC 10 confirmée, facture 10 000 HT / 12 000 TTC saisie + PATCH bon_commande (lettre la
provision), POST receptions-fournisseur/<id>/annuler/. (T) témoin : la même chaîne avec « Facturer » la
réception (FG56) → annulation refusée 400. Attendu sain (R) : 400 aussi, ou facture passée en exception."""
SONDE = {"constat": "C-AAPV-003", "sha": "5f603acce0",
         "attendu": "repro si R : annuler 200, stock 0, recu 0, facture 12000 TTC normale et payable, provision lettree sur reception annulee ; T : 400",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.ReceptionFournisseur",
                     "stock.FactureFournisseur", "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur, Produit,
                                   FactureFournisseur, ReceptionFournisseur)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 003', slug='sonde-aapv-003')
    u = get_user_model().objects.create_user(username='sonde_aapv_003', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV3')
    url = '/api/django/stock/receptions-fournisseur/'

    def chaine(tag, via_fg56):
        p = Produit.objects.create(company=co, nom=f'Batterie AAPV3 {tag}', sku=f'AAPV-003-{tag}',
                                   prix_vente=Decimal('2000'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-003-{tag}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('1000'))
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        rec_id = r.data['id']
        rc = api.post(f'{url}{rec_id}/confirmer/', {}, format='json', **H)
        o = {'confirmer': rc.status_code}
        if via_fg56:
            rf = api.post(f'{url}{rec_id}/facturer/', {}, format='json', **H)
            o['facture'] = rf.status_code
            fid = rf.data.get('id')
        else:
            rf = api.post('/api/django/stock/factures-fournisseur/', {
                'fournisseur': f.id, 'ref_fournisseur': f'OCR-{tag}', 'date_facture': timezone.now().date().isoformat(),
                'montant_ht': '10000.00', 'montant_tva': '2000.00', 'montant_ttc': '12000.00'}, format='json', **H)
            fid = rf.data.get('id')
            rp = api.patch(f'/api/django/stock/factures-fournisseur/{fid}/', {'bon_commande': bc.id},
                           format='json', **H)
            o['facture'] = (rf.status_code, rp.status_code)
        o['gr_ir_avant_annul'] = [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
            company=co, bon_commande=bc).values('montant_provision', 'lettre')]
        with TestCase.captureOnCommitCallbacks(execute=True):
            ra = api.post(f'{url}{rec_id}/annuler/', {}, format='json', **H)
        p.refresh_from_db()
        lc.refresh_from_db()
        fa = FactureFournisseur.objects.get(pk=fid)
        o.update({'annuler_http': ra.status_code,
                  'detail': None if ra.status_code < 400 else str(ra.data)[:160],
                  'reception_statut': ReceptionFournisseur.objects.get(pk=rec_id).statut,
                  'stock': p.quantite_stock, 'bcf_recu': lc.quantite_recue,
                  'facture_ttc': str(fa.montant_ttc), 'facture_solde_du': str(fa.solde_du),
                  'facture_statut_controle': fa.statut_controle, 'facture_reception_id': fa.reception_id,
                  'gr_ir_apres_annul': [{k: str(v) for k, v in d.items()} for d in ReceptionNonFacturee.objects.filter(
                      company=co, bon_commande=bc).values('montant_provision', 'lettre', 'reception_id')]})
        return o

    obs = {'R_ocr_patch': chaine('R', False), 'T_fg56': chaine('T', True)}
    print(obs)
    R, T = obs['R_ocr_patch'], obs['T_fg56']
    temoin_ok = T['confirmer'] == 200 and T['annuler_http'] == 400 and T['stock'] == 10
    defaut = (R['confirmer'] == 200 and R['facture'] == (201, 200) and R['annuler_http'] == 200
              and R['stock'] == 0 and R['bcf_recu'] == 0 and R['facture_statut_controle'] == 'normale'
              and Decimal(R['facture_solde_du']) == Decimal('12000'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
