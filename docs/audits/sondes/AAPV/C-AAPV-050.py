# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K50 — `facturer_bcf_sur_commande` (POST bons-commande-fournisseur/<id>/facturer/, ZPUR1) ne lit pas le
statut du BCF ; `annuler` (POST …/annuler/) et `annuler_bcf_cascade` ignorent factures et acomptes.
Produit « sur commande », BCF 10 × 2 000 HT. (R1) BCF annulé (motif) puis facturer. (R2) BCF BROUILLON
facturer. (R3) BCF ENVOYE facturé + acompte 30 % (7 200) puis annulé : la réponse « cascade » et l'état de
la facture/acompte. Le double clic concurrent (idempotence lue hors verrou) n'est pas rejouable dans une
transaction annulée : lu seulement. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-050", "sha": "5f603acce",
         "attendu": "repro si R1 facturer = 201 sur un BCF annulé (FF payable) ; R3 annulation 200 sans signaler la facture ni l'acompte",
         "modeles": ["achats.FactureFournisseur", "achats.BonCommandeFournisseur", "stock.AcompteFournisseur"]}

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
    from apps.achats.models import FactureFournisseur, BonCommandeFournisseur
    co, u, api, f, p = _base('aapv-050')
    p.politique_facturation_achat = 'sur_commande'
    p.save(update_fields=['politique_facturation_achat'])
    obs = {}
    b1, _l = _bcf(co, f, p, 'BCF-AAPV-050-R1', qte=10, pu='2000')
    ra = api.post(f'/api/django/stock/bons-commande-fournisseur/{b1.id}/annuler/', {'motif_annulation': 'erreur'},
                  format='json', **H)
    b1.refresh_from_db()
    rf = api.post(f'/api/django/stock/bons-commande-fournisseur/{b1.id}/facturer/', {}, format='json', **H)
    obs['R1'] = {'annuler': ra.status_code, 'statut_bcf': b1.statut, 'facturer': rf.status_code,
                 'ttc': rf.data.get('montant_ttc') if rf.status_code < 400 else str(rf.data)[:120],
                 'solde_du': rf.data.get('solde_du') if rf.status_code < 400 else None}
    if rf.status_code == 201:
        rp = api.post('/api/django/stock/paiements-fournisseur/',
                      {'facture': rf.data['id'], 'montant': '1000.00', 'date_paiement': '2026-11-03',
                       'mode': 'virement'}, format='json', **H)
        obs['R1']['paiement_partiel_http'] = rp.status_code
    b2, _l2 = _bcf(co, f, p, 'BCF-AAPV-050-R2', qte=10, pu='2000')
    BonCommandeFournisseur.objects.filter(pk=b2.pk).update(statut='brouillon')
    rf2 = api.post(f'/api/django/stock/bons-commande-fournisseur/{b2.id}/facturer/', {}, format='json', **H)
    obs['R2_brouillon_facturer'] = rf2.status_code
    b3, _l3 = _bcf(co, f, p, 'BCF-AAPV-050-R3', qte=10, pu='2000')
    rf3 = api.post(f'/api/django/stock/bons-commande-fournisseur/{b3.id}/facturer/', {}, format='json', **H)
    rac = api.post('/api/django/stock/acomptes-fournisseur/',
                   {'bon_commande': b3.id, 'montant': '7200.00', 'date_versement': '2026-11-03'}, format='json', **H)
    rn = api.post(f'/api/django/stock/bons-commande-fournisseur/{b3.id}/annuler/', {'motif_annulation': 'abandon'},
                  format='json', **H)
    fac3 = FactureFournisseur.objects.get(pk=rf3.data['id'])
    obs['R3'] = {'facturer': rf3.status_code, 'acompte': rac.status_code, 'annuler': rn.status_code,
                 'cascade': rn.data.get('cascade') if rn.status_code < 400 else str(rn.data)[:120],
                 'facture_apres': (fac3.statut, str(fac3.montant_ttc), str(fac3.solde_du),
                                   str(fac3.total_acomptes_imputes))}
    # double facturation séquentielle : la garde d'idempotence existe (marqueur de note)
    rf3b = api.post(f'/api/django/stock/bons-commande-fournisseur/{b3.id}/facturer/', {}, format='json', **H)
    obs['R3_refacturer_sequentiel'] = rf3b.status_code
    print(obs)
    obs['repro'] = bool(obs['R1']['statut_bcf'] == 'annule' and rf.status_code == 201)
    return obs
