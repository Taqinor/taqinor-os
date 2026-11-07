# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K44 — verrou ASTK26 (`FactureFournisseurSerializer._a_une_imputation`) lit la FK héritée
`acomptes_imputes` (AcompteFournisseur.facture_imputee = PREMIÈRE facture servie) au lieu de la table
`imputations_acompte` (ASTK106). BCF 2 × 2 500 HT ; acompte 5 000 versé ; réception 1 → FG56 F1 (TTC 3 000,
reçoit 3 000) ; réception 1 → FG56 F2 (TTC 3 000, reçoit 2 000). PATCH F2 {bon_commande: null} puis
{montant_ttc: 500}. (T) témoin : PATCH F1 {bon_commande: null} → 409 « Facture réglée ».
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-044", "sha": "5f603acce",
         "attendu": "repro si F2 : délier 200 puis TTC 500 accepté 200 (F2 « payee », acompte consommé 5000) ; T : 409",
         "modeles": ["achats.FactureFournisseur", "stock.AcompteFournisseur", "achats.ImputationAcompteFournisseur"]}

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
    from apps.achats.models import FactureFournisseur
    from apps.stock.models import AcompteFournisseur
    co, u, api, f, p = _base('aapv-044')
    obs = {}
    bc, ligne = _bcf(co, f, p, 'BCF-AAPV-044', qte=2, pu='2500')
    ra = api.post('/api/django/stock/acomptes-fournisseur/',
                  {'bon_commande': bc.id, 'montant': '5000.00', 'date_versement': '2026-11-01'}, format='json', **H)
    r1 = _recevoir(api, co, bc, ligne, 1, 'REC-AAPV-044-1')
    f1 = api.post(f'/api/django/stock/receptions-fournisseur/{r1.id}/facturer/', {}, format='json', **H).data['id']
    r2 = _recevoir(api, co, bc, ligne, 1, 'REC-AAPV-044-2')
    f2 = api.post(f'/api/django/stock/receptions-fournisseur/{r2.id}/facturer/', {}, format='json', **H).data['id']
    ac = AcompteFournisseur.objects.get(pk=ra.data['id'])
    F1, F2 = FactureFournisseur.objects.get(pk=f1), FactureFournisseur.objects.get(pk=f2)
    obs['avant'] = {'F1': (str(F1.montant_ttc), str(F1.total_acomptes_imputes), F1.statut),
                    'F2': (str(F2.montant_ttc), str(F2.total_acomptes_imputes), F2.statut),
                    'acompte_fk_facture_imputee': ac.facture_imputee_id == f1,
                    'acompte_consomme': str(ac.montant_consomme)}
    p1 = api.patch(f'/api/django/stock/factures-fournisseur/{f2}/', {'bon_commande': None}, format='json', **H)
    obs['F2_delier'] = (p1.status_code, None if p1.status_code < 400 else str(p1.data)[:120])
    p2 = api.patch(f'/api/django/stock/factures-fournisseur/{f2}/', {'montant_ttc': '500.00'}, format='json', **H)
    obs['F2_ttc_500'] = (p2.status_code, None if p2.status_code < 400 else str(p2.data)[:120])
    F2 = FactureFournisseur.objects.get(pk=f2)
    ac.refresh_from_db()
    obs['apres'] = {'F2_ttc': str(F2.montant_ttc), 'F2_bcf': F2.bon_commande_id, 'F2_statut': F2.statut,
                    'F2_solde': str(F2.solde_du), 'F2_imputations': str(F2.total_acomptes_imputes),
                    'acompte_consomme': str(ac.montant_consomme),
                    'credit_perdu': str(F2.total_acomptes_imputes - F2.montant_ttc)}
    t = api.patch(f'/api/django/stock/factures-fournisseur/{f1}/', {'bon_commande': None}, format='json', **H)
    obs['T_F1_delier'] = (t.status_code, None if t.status_code < 400 else str(t.data)[:120])
    print(obs)
    temoin_ok = t.status_code == 409
    defaut = p1.status_code == 200 and p2.status_code == 200
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
