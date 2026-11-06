# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K40 — une facture fournisseur saisie/OCR SANS BCF puis liée par PATCH {bon_commande} (geste « Lier au
BCF » d'OcrUpload.jsx) n'impute pas l'acompte déjà versé sur ce BCF. Chaîne API réelle : BCF 10 × 1 000 HT,
POST acomptes-fournisseur 3 600, réception 10 confirmée (POST …/confirmer/), POST factures-fournisseur
(TTC 12 000, sans BCF), PATCH {bon_commande}, puis POST paiements-fournisseur 12 000.
(T) témoin : même BCF/acompte, facture par POST receptions-fournisseur/<id>/facturer/ (FG56) → acompte imputé.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-040", "sha": "5f603acce",
         "attendu": "repro si PATCH : total_acomptes_imputes 0, solde_du 12000, paiement 12000 accepté (201), acompte encore ouvert 3600 ; T : solde_du 8400",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "stock.AcompteFournisseur",
                     "achats.ImputationAcompteFournisseur", "achats.ReceptionFournisseur"]}

H = {'HTTP_HOST': 'localhost'}


def _base(slug):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur
    co = Company.objects.create(nom='Sonde ' + slug, slug='sonde-' + slug)
    u = get_user_model().objects.create_user(username='sonde-' + slug, password='x', company=co,
                                             role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='Fournisseur ' + slug)
    p = Produit.objects.create(company=co, nom='Onduleur ' + slug, sku='SONDE-' + slug.upper(),
                               prix_vente=Decimal('2000'), quantite_stock=0, tva=Decimal('20.00'))
    return co, u, api, f, p


def _bcf(co, f, p, ref, qte=10, pu='1000'):
    import datetime
    from decimal import Decimal
    from apps.achats.models import BonCommandeFournisseur, LigneBonCommandeFournisseur
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=ref,
                                               statut=BonCommandeFournisseur.Statut.ENVOYE,
                                               date_commande=datetime.date.today())
    ligne = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=qte,
                                                       prix_achat_unitaire=Decimal(pu))
    return bc, ligne


def _recevoir(api, co, bc, ligne, qte, ref):
    import datetime
    from apps.achats.models import ReceptionFournisseur, LigneReceptionFournisseur
    r = ReceptionFournisseur.objects.create(company=co, reference=ref, bon_commande=bc,
                                            date_reception=datetime.date.today())
    LigneReceptionFournisseur.objects.create(reception=r, ligne_commande=ligne, produit=ligne.produit, quantite=qte)
    resp = api.post(f'/api/django/stock/receptions-fournisseur/{r.id}/confirmer/', {}, format='json', **H)
    assert resp.status_code == 200, (resp.status_code, getattr(resp, 'data', None))
    r.refresh_from_db()
    return r


def sonde(ctx):
    from decimal import Decimal
    from apps.achats.models import FactureFournisseur
    from apps.stock.models import AcompteFournisseur
    co, u, api, f, p = _base('aapv-040')
    obs = {}

    # R — facture saisie sans BCF puis liée par PATCH.
    bc, ligne = _bcf(co, f, p, 'BCF-AAPV-040-R')
    ra = api.post('/api/django/stock/acomptes-fournisseur/',
                  {'bon_commande': bc.id, 'montant': '3600.00', 'date_versement': '2026-11-01'}, format='json', **H)
    obs['acompte_http'] = ra.status_code
    _recevoir(api, co, bc, ligne, 10, 'REC-AAPV-040-R')
    rf = api.post('/api/django/stock/factures-fournisseur/',
                  {'fournisseur': f.id, 'ref_fournisseur': 'F-OCR-040', 'date_facture': '2026-11-02',
                   'montant_ht': '10000.00', 'montant_tva': '2000.00', 'montant_ttc': '12000.00'},
                  format='json', **H)
    obs['facture_http'] = rf.status_code
    fid = rf.data['id']
    rp = api.patch(f'/api/django/stock/factures-fournisseur/{fid}/', {'bon_commande': bc.id}, format='json', **H)
    obs['patch_http'] = rp.status_code
    fac = FactureFournisseur.objects.get(pk=fid)
    obs['R_total_acomptes_imputes'] = str(fac.total_acomptes_imputes)
    obs['R_solde_du_apres_lien'] = str(fac.solde_du)
    obs['R_statut_controle'] = fac.statut_controle
    rpay = api.post('/api/django/stock/paiements-fournisseur/',
                    {'facture': fid, 'montant': '12000.00', 'date_paiement': '2026-11-03', 'mode': 'virement'},
                    format='json', **H)
    obs['R_paiement_12000_http'] = rpay.status_code
    obs['R_paiement_detail'] = None if rpay.status_code < 400 else str(rpay.data)[:160]
    ac = AcompteFournisseur.objects.get(pk=ra.data['id'])
    obs['R_acompte_non_consomme'] = str(ac.montant_non_consomme)
    ouverts = api.get('/api/django/stock/acomptes-fournisseur/ouverts/', **H)
    obs['R_acompte_liste_ouvert'] = ac.id in [x.get('id') for x in (ouverts.data if isinstance(ouverts.data, list)
                                                                     else ouverts.data.get('results', []))]
    fac = FactureFournisseur.objects.get(pk=fid)
    obs['R_decaisse_total'] = str(fac.total_paye + ac.montant)

    # T — témoin FG56 : la facture née de la réception impute l'acompte.
    bt, lt = _bcf(co, f, p, 'BCF-AAPV-040-T')
    api.post('/api/django/stock/acomptes-fournisseur/',
             {'bon_commande': bt.id, 'montant': '3600.00', 'date_versement': '2026-11-01'}, format='json', **H)
    rt = _recevoir(api, co, bt, lt, 10, 'REC-AAPV-040-T')
    rft = api.post(f'/api/django/stock/receptions-fournisseur/{rt.id}/facturer/', {}, format='json', **H)
    obs['T_facturer_http'] = rft.status_code
    ft = FactureFournisseur.objects.get(pk=rft.data['id'])
    obs['T_ttc'] = str(ft.montant_ttc)
    obs['T_total_acomptes_imputes'] = str(ft.total_acomptes_imputes)
    obs['T_solde_du'] = str(ft.solde_du)
    print(obs)
    temoin_ok = Decimal(obs['T_solde_du']) == Decimal('8400')
    defaut = (obs['patch_http'] == 200 and Decimal(obs['R_total_acomptes_imputes']) == 0
              and Decimal(obs['R_solde_du_apres_lien']) == Decimal('12000'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
