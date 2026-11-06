# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K43 — RAS-TVA fournisseur (`compute_ras_tva`, ras_tva_actif=True, biens, fournisseur sans ARF → 100 %).
Factures FG56 TTC 1 200 / TVA 200 (BCF 1 × 1 000 HT, réception confirmée, POST …/facturer/).
(B) paiement 840 PUIS acompte 360 (POST acomptes-fournisseur → imputé, ERR-ASTK106) : D-ASTK-171 attend Σ RAS 200.
(TB) témoin : acompte 360 PUIS paiement 840 (exemple du docstring) → 200.
(A) avoir 600 TTC (TVA 100) validé + imputé PUIS paiement 600 : Σ RAS observé ; selon D-AARG-2 « tva_nette »
transposé au fournisseur, attendu 100 — DÉCISION FONDATEUR à confirmer (D-AARG-2 tranché côté client seulement).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-043", "sha": "5f603acce",
         "attendu": "repro (b) si facture payée avec Σ RAS 140 au lieu de 200, témoin 200 ; (a) relevé seul : 200 observé vs 100 si tva_nette",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "stock.AcompteFournisseur",
                     "stock.AvoirFournisseur", "stock.AchatsParametres"]}

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
    from apps.stock.models import AchatsParametres
    co, u, api, f, p = _base('aapv-043')
    ap = AchatsParametres.for_company(co)
    ap.ras_tva_actif = True
    ap.save()
    obs = {}

    def facture(tag):
        bc, ligne = _bcf(co, f, p, f'BCF-AAPV-043-{tag}', qte=1, pu='1000')
        rec = _recevoir(api, co, bc, ligne, 1, f'REC-AAPV-043-{tag}')
        r = api.post(f'/api/django/stock/receptions-fournisseur/{rec.id}/facturer/', {}, format='json', **H)
        assert r.status_code == 201, r.data
        return bc, r.data['id']

    def payer(fid, m):
        r = api.post('/api/django/stock/paiements-fournisseur/',
                     {'facture': fid, 'montant': m, 'date_paiement': '2026-11-03', 'mode': 'virement'},
                     format='json', **H)
        return r.status_code, (r.data.get('montant_ras_tva') if r.status_code < 400 else str(r.data)[:120])

    def acompte(bc, m):
        return api.post('/api/django/stock/acomptes-fournisseur/',
                        {'bon_commande': bc.id, 'montant': m, 'date_versement': '2026-11-03'},
                        format='json', **H).status_code

    def bilan(fid):
        fac = FactureFournisseur.objects.get(pk=fid)
        return {'statut': fac.statut, 'solde_du': str(fac.solde_du),
                'ras_total': str(sum((x.montant_ras_tva for x in fac.paiements.all()), Decimal('0'))),
                'net_decaisse': str(sum((x.montant_net_paye for x in fac.paiements.all()), Decimal('0')))}

    bcb, fb = facture('B')
    obs['B_paiement_840'] = payer(fb, '840.00')
    obs['B_acompte_360'] = acompte(bcb, '360.00')
    obs['B'] = bilan(fb)
    bct, ft = facture('TB')
    obs['TB_acompte_360'] = acompte(bct, '360.00')
    obs['TB_paiement_840'] = payer(ft, '840.00')
    obs['TB'] = bilan(ft)
    bca, fa = facture('A')
    rc = api.post('/api/django/stock/avoirs-fournisseur/',
                  {'fournisseur': f.id, 'montant_ht': '500.00', 'montant_tva': '100.00', 'montant_ttc': '600.00'},
                  format='json', **H)
    api.post(f'/api/django/stock/avoirs-fournisseur/{rc.data["id"]}/valider/', {}, format='json', **H)
    ri = api.post(f'/api/django/stock/avoirs-fournisseur/{rc.data["id"]}/imputer/', {'facture': fa}, format='json', **H)
    obs['A_imputer_avoir'] = ri.status_code
    obs['A_paiement_600'] = payer(fa, '600.00')
    obs['A'] = bilan(fa)
    print(obs)
    temoin_ok = obs['TB']['statut'] == 'payee' and Decimal(obs['TB']['ras_total']) == Decimal('200')
    defaut_b = obs['B']['statut'] == 'payee' and Decimal(obs['B']['ras_total']) < Decimal('200')
    obs['temoin_ok'] = temoin_ok
    obs['A_ecart_si_tva_nette'] = str(Decimal(obs['A']['ras_total']) - Decimal('100'))
    obs['repro'] = bool(temoin_ok and defaut_b)
    return obs
