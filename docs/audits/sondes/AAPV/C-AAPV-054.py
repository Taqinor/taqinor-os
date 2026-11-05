# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K54 — `imputer_avoir_sous_verrou` verrouille l'AVOIR seul et lit `facture.solde_du` sans verrou de la
facture ; la porte paiement (`verrouiller_facture_fournisseur_et_verifier_solde`) ne voit pas une imputation
en cours. Deux transactions réelles ne sont pas rejouables dans la transaction annulée du lanceur : on
REJOUE L'ENTRELACEMENT sur une connexion — l'imputation d'avoir (POST avoirs-fournisseur/<id>/imputer/) lit
le solde 1 000, puis (crochet posé sur `ImputationAvoirFournisseur.objects.create`, juste avant l'écriture)
le POST paiements-fournisseur 1 000 complet passe sous son verrou, puis l'imputation s'écrit. Sous Postgres
READ COMMITTED cet ordre est atteignable : la lecture du solde côté avoir ne prend aucun verrou de facture.
(T) témoin séquentiel : paiement 1 000 puis imputer → 409 « Rien à imputer ».
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-054", "sha": "5f603acce",
         "attendu": "repro si R : paiement 201 + imputation 200 → Σ paiements + avoirs imputés 2000 pour TTC 1000 ; T : 409",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "stock.AvoirFournisseur",
                     "stock.ImputationAvoirFournisseur"]}

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
    from apps.stock.models import ImputationAvoirFournisseur
    co, u, api, f, p = _base('aapv-054')
    obs = {}

    def facture_et_avoir(tag):
        rf = api.post('/api/django/stock/factures-fournisseur/',
                      {'fournisseur': f.id, 'ref_fournisseur': f'F-054-{tag}', 'date_facture': '2026-11-02',
                       'montant_ht': '1000.00', 'montant_tva': '0.00', 'montant_ttc': '1000.00'}, format='json', **H)
        ra = api.post('/api/django/stock/avoirs-fournisseur/',
                      {'fournisseur': f.id, 'montant_ht': '1000.00', 'montant_tva': '0.00', 'montant_ttc': '1000.00'},
                      format='json', **H)
        api.post(f'/api/django/stock/avoirs-fournisseur/{ra.data["id"]}/valider/', {}, format='json', **H)
        return rf.data['id'], ra.data['id']

    def payer(fid):
        return api.post('/api/django/stock/paiements-fournisseur/',
                        {'facture': fid, 'montant': '1000.00', 'date_paiement': '2026-11-03', 'mode': 'virement'},
                        format='json', **H).status_code

    def bilan(fid):
        fac = FactureFournisseur.objects.get(pk=fid)
        return {'ttc': str(fac.montant_ttc), 'paye': str(fac.total_paye), 'avoirs': str(fac.total_avoirs_imputes),
                'regle_total': str(fac.total_paye + fac.total_avoirs_imputes), 'solde_du': str(fac.solde_du),
                'statut': fac.statut}

    # R — entrelacement.
    fid, aid = facture_et_avoir('R')
    mgr = ImputationAvoirFournisseur.objects
    orig = mgr.create
    etat = {'paiement': None}

    def crochet(*a, **k):
        if etat['paiement'] is None:
            etat['paiement'] = payer(fid)   # transaction B passe pendant la fenêtre de A
        return orig(*a, **k)

    mgr.create = crochet
    try:
        ri = api.post(f'/api/django/stock/avoirs-fournisseur/{aid}/imputer/', {'facture': fid}, format='json', **H)
    finally:
        mgr.create = orig
    obs['R'] = {'paiement_pendant': etat['paiement'], 'imputer': ri.status_code, **bilan(fid)}
    # T — séquentiel.
    ft, at = facture_et_avoir('T')
    tp = payer(ft)
    ti = api.post(f'/api/django/stock/avoirs-fournisseur/{at}/imputer/', {'facture': ft}, format='json', **H)
    obs['T'] = {'paiement': tp, 'imputer': ti.status_code, **bilan(ft)}
    print(obs)
    temoin_ok = tp == 201 and ti.status_code == 409
    defaut = (etat['paiement'] == 201 and ri.status_code == 200
              and Decimal(obs['R']['regle_total']) > Decimal(obs['R']['ttc']))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
