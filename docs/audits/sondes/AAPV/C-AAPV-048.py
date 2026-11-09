# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K48 — FG56 (`facturer_reception`) et le 3 voies (`_montant_attendu_bcf_ht`) lisent les lignes de réception,
jamais modifiées par un retour fournisseur. BCF 10 × 1 000 HT ; réception 10 confirmée ; retour de 3 validé
AVANT facture (POST retours-fournisseur/<id>/valider/, YPROC8 rouvre quantite_recue → 7) ; puis POST
receptions-fournisseur/<id>/facturer/. Attendu : facture 7 000 HT ou exception. Puis paiement du TTC.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-048", "sha": "5f603acce",
         "attendu": "repro si la facture FG56 vaut 10000 HT, reste « normale » et se paie 12000 alors que quantite_recue = 7",
         "modeles": ["achats.FactureFournisseur", "achats.RetourFournisseur", "achats.PaiementFournisseur",
                     "stock.MouvementStock"]}

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
    from apps.achats.models import FactureFournisseur, RetourFournisseur, LigneRetourFournisseur
    from apps.stock.selectors import montant_recu_bcf
    from apps.stock.services import _montant_attendu_bcf_ht
    co, u, api, f, p = _base('aapv-048')
    obs = {}
    bc, ligne = _bcf(co, f, p, 'BCF-AAPV-048')
    rec = _recevoir(api, co, bc, ligne, 10, 'REC-AAPV-048')
    ret = RetourFournisseur.objects.create(company=co, reference='RTF-AAPV-048', fournisseur=f, bon_commande=bc,
                                           motif='3 défectueux')
    LigneRetourFournisseur.objects.create(retour=ret, produit=p, quantite=3, motif='défaut')
    rv = api.post(f'/api/django/stock/retours-fournisseur/{ret.id}/valider/', {}, format='json', **H)
    obs['retour_valider'] = (rv.status_code, None if rv.status_code < 400 else str(rv.data)[:120])
    ligne.refresh_from_db()
    p.refresh_from_db()
    obs['quantite_recue_bcf'] = ligne.quantite_recue
    obs['stock'] = p.quantite_stock
    obs['montant_recu_bcf_YPROC8'] = str(montant_recu_bcf(bc))
    rf = api.post(f'/api/django/stock/receptions-fournisseur/{rec.id}/facturer/', {}, format='json', **H)
    obs['facturer'] = rf.status_code
    fac = FactureFournisseur.objects.get(pk=rf.data['id'])
    obs['facture'] = {'ht': str(fac.montant_ht), 'ttc': str(fac.montant_ttc), 'statut_controle': fac.statut_controle}
    obs['attendu_3voies'] = str(_montant_attendu_bcf_ht(bc.id))
    rpay = api.post('/api/django/stock/paiements-fournisseur/',
                    {'facture': fac.id, 'montant': str(fac.montant_ttc), 'date_paiement': '2026-11-03',
                     'mode': 'virement'}, format='json', **H)
    obs['paiement_ttc_http'] = rpay.status_code
    print(obs)
    obs['repro'] = bool(rv.status_code == 200 and ligne.quantite_recue == 7 and fac.montant_ht == 10000
                        and fac.statut_controle == 'normale' and rpay.status_code == 201)
    return obs
