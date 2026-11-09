# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K42 — le relevé de déductions TVA (GET factures-fournisseur/releve-deductions-tva/) n'additionne que les
lignes ventilées : une facture saisie à l'écran (sans lignes) et un avoir fournisseur imputé n'y figurent pas.
Même mois : (A) facture FG56 (POST receptions/<id>/facturer/, 10 × 1 000 HT, TVA 2 000, lignes à 20 %) ;
(B) facture POST factures-fournisseur sans lignes (HT 2 000 / TVA 400) ; (C) avoir POST avoirs-fournisseur
(TVA 200), valider, imputer sur A. Attendu : TVA déductible 2 200 (2 000 + 400 − 200).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-042", "sha": "5f603acce",
         "attendu": "repro si le relevé affiche total_tva 2000 (B et l'avoir ignorés) au lieu de 2200",
         "modeles": ["achats.FactureFournisseur", "stock.AvoirFournisseur", "stock.ImputationAvoirFournisseur"]}

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
    import datetime
    from decimal import Decimal
    co, u, api, f, p = _base('aapv-042')
    today = datetime.date.today()
    debut, fin = today.replace(day=1).isoformat(), today.isoformat()
    obs = {}
    bc, ligne = _bcf(co, f, p, 'BCF-AAPV-042')
    rec = _recevoir(api, co, bc, ligne, 10, 'REC-AAPV-042')
    ra = api.post(f'/api/django/stock/receptions-fournisseur/{rec.id}/facturer/', {}, format='json', **H)
    obs['A'] = (ra.status_code, ra.data.get('montant_tva'), len(ra.data.get('lignes') or []))
    rb = api.post('/api/django/stock/factures-fournisseur/',
                  {'fournisseur': f.id, 'ref_fournisseur': 'F-042-B', 'date_facture': fin,
                   'montant_ht': '2000.00', 'montant_tva': '400.00', 'montant_ttc': '2400.00'}, format='json', **H)
    obs['B'] = (rb.status_code, rb.data.get('montant_tva'), len(rb.data.get('lignes') or []))
    rc = api.post('/api/django/stock/avoirs-fournisseur/',
                  {'fournisseur': f.id, 'montant_ht': '1000.00', 'montant_tva': '200.00', 'montant_ttc': '1200.00'},
                  format='json', **H)
    rv = api.post(f'/api/django/stock/avoirs-fournisseur/{rc.data["id"]}/valider/', {}, format='json', **H)
    ri = api.post(f'/api/django/stock/avoirs-fournisseur/{rc.data["id"]}/imputer/', {'facture': ra.data['id']},
                  format='json', **H)
    obs['avoir'] = (rc.status_code, rv.status_code, ri.status_code, ri.data.get('statut'))
    rr = api.get(f'/api/django/stock/factures-fournisseur/releve-deductions-tva/?date_debut={debut}&date_fin={fin}',
                 **H)
    obs['releve_http'] = rr.status_code
    obs['releve'] = [{k: str(v) for k, v in e.items()} for e in (rr.data or [])]
    total = sum((Decimal(str(e['total_tva'])) for e in (rr.data or [])), Decimal('0'))
    obs['releve_total_tva'] = str(total)
    obs['attendu_total_tva'] = '2200.00'
    print(obs)
    obs['repro'] = bool(rr.status_code == 200 and total != Decimal('2200') and obs['B'][0] == 201
                        and obs['avoir'][2] == 200)
    return obs
