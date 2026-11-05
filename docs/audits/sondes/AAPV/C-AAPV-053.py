# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K53 — achats en devise. (R1) BCF EUR taux 10,80, ligne 100 EUR (= 1 080 MAD), réception 10 confirmée,
POST receptions/<id>/facturer/ (`_construire_facture_fournisseur`) : la facture garde-t-elle devise/taux/TTC
devise ? Puis règlement au taux du jour 11,00 (1 200 EUR × 11 = 13 200 MAD) : accepté ? (R2) POST
factures-fournisseur {montant_ht 1000, montant_tva 200, montant_ttc_devise 1200, devise EUR, taux 10,8} :
seul le TTC est converti ; avec ras_tva_actif (biens, sans ARF) le paiement du TTC retient 200 au lieu de 2 160.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-053", "sha": "5f603acce",
         "attendu": "repro si R1 facture.devise == MAD (EUR perdu) et paiement 13200 refusé ; R2 HT/TVA restent 1000/200 pour TTC 12960 MAD et RAS 200",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "stock.AchatsParametres"]}

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
    from apps.achats.models import FactureFournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur
    from apps.stock.models import AchatsParametres
    co, u, api, f, p = _base('aapv-053')
    ap = AchatsParametres.for_company(co)
    ap.ras_tva_actif = True
    ap.save()
    obs = {}
    bc, ligne = _bcf(co, f, p, 'BCF-AAPV-053', qte=10, pu='1080')
    BonCommandeFournisseur.objects.filter(pk=bc.pk).update(devise='EUR', taux_change=Decimal('10.8'))
    LigneBonCommandeFournisseur.objects.filter(pk=ligne.pk).update(prix_achat_unitaire_devise=Decimal('100'))
    bc.refresh_from_db()
    rec = _recevoir(api, co, bc, ligne, 10, 'REC-AAPV-053')
    rf = api.post(f'/api/django/stock/receptions-fournisseur/{rec.id}/facturer/', {}, format='json', **H)
    fac = FactureFournisseur.objects.get(pk=rf.data['id'])
    obs['R1_bcf'] = (bc.devise, str(bc.taux_change))
    obs['R1_facture'] = {'devise': fac.devise, 'taux': str(fac.taux_change),
                         'ttc_devise': str(fac.montant_ttc_devise), 'ht': str(fac.montant_ht),
                         'ttc': str(fac.montant_ttc)}
    rp = api.post('/api/django/stock/paiements-fournisseur/',
                  {'facture': fac.id, 'montant': '13200.00', 'date_paiement': '2026-11-03', 'mode': 'virement'},
                  format='json', **H)
    obs['R1_paiement_taux_11'] = (rp.status_code, None if rp.status_code < 400 else str(rp.data)[:140])
    r2 = api.post('/api/django/stock/factures-fournisseur/',
                  {'fournisseur': f.id, 'ref_fournisseur': 'F-053-2', 'date_facture': '2026-11-02',
                   'montant_ht': '1000.00', 'montant_tva': '200.00', 'montant_ttc_devise': '1200.00',
                   'devise': 'EUR', 'taux_change': '10.8'}, format='json', **H)
    obs['R2_creation'] = r2.status_code
    f2 = FactureFournisseur.objects.get(pk=r2.data['id'])
    obs['R2_facture'] = {'ht': str(f2.montant_ht), 'tva': str(f2.montant_tva), 'ttc': str(f2.montant_ttc),
                         'devise': f2.devise}
    rp2 = api.post('/api/django/stock/paiements-fournisseur/',
                   {'facture': f2.id, 'montant': str(f2.montant_ttc), 'date_paiement': '2026-11-03',
                    'mode': 'virement'}, format='json', **H)
    obs['R2_paiement'] = (rp2.status_code, rp2.data.get('montant_ras_tva') if rp2.status_code < 400 else str(rp2.data)[:120])
    obs['R2_ras_attendue'] = '2160.00'
    print(obs)
    obs['repro'] = bool(fac.devise == 'MAD' and rp.status_code >= 400 and f2.montant_ht == 1000
                        and f2.montant_ttc == Decimal('12960'))
    return obs
