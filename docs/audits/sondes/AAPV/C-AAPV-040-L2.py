# flake8: noqa  (seconde lentille PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §B.5)
"""K40 / seconde lentille — les VRAIES routes de l'écran, rôle responsable.
La sonde d'origine (C-AAPV-040, admin) créait la facture par POST factures-fournisseur/ (saisie manuelle, qu'aucun
écran ne peut ensuite lier) et payait par POST paiements-fournisseur/. Ici, la chaîne de l'écran :
FournisseurFiche360.jsx::AcompteForm (POST acomptes-fournisseur/), réception confirmée, OcrUpload.jsx ::
createFactureFromDocument (POST factures-fournisseur/depuis-ocr/ {fields}) → getSuggestionsBcfFacture (GET
suggestions-bcf/) → confirmerBcf (PATCH {bon_commande}) ; FacturesFournisseur.jsx::FactureDetail « Régler le solde »
(montant = solde_du affiché) → POST factures-fournisseur/<id>/paiements/.
Attendu sain : solde_du affiché 8 400 (acompte 3 600 imputé) ; paiement de 12 000 refusé."""
SONDE = {"constat": "C-AAPV-040", "sha": "ff075ef7d4",
         "attendu": "repro si (responsable, route OCR) solde_du 12000 apres lien, BCF propose par suggestions, paiement ecran 12000 accepte, acompte 3600 non consomme",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "stock.AcompteFournisseur",
                     "achats.ImputationAcompteFournisseur", "achats.ReceptionFournisseur"]}

H = {'HTTP_HOST': 'localhost'}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.achats.models import (BonCommandeFournisseur, LigneBonCommandeFournisseur, ReceptionFournisseur,
                                    LigneReceptionFournisseur, FactureFournisseur)
    from apps.stock.models import Produit, Fournisseur, AcompteFournisseur
    co = Company.objects.create(nom='Sonde AAPV 040 L2', slug='sonde-aapv-040-l2')
    u = get_user_model().objects.create_user(username='sonde_aapv_040_l2', password='x', company=co,
                                             role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='Fournisseur AAPV40L2')
    p = Produit.objects.create(company=co, nom='Onduleur AAPV40L2', sku='SONDE-AAPV40L2',
                               prix_vente=Decimal('2000'), quantite_stock=0, tva=Decimal('20.00'))
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-040-L2',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE,
                                               date_commande=datetime.date.today())
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                    prix_achat_unitaire=Decimal('1000'))
    obs = {'role': 'responsable'}
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra = api.post('/api/django/stock/acomptes-fournisseur/',
                      {'bon_commande': bc.id, 'montant': 3600, 'date_versement': None, 'mode': 'virement',
                       'note': None}, format='json', **H)
    obs['acompte_http'] = ra.status_code
    obs['acompte_detail'] = None if ra.status_code < 400 else str(ra.data)[:160]
    r = ReceptionFournisseur.objects.create(company=co, reference='REC-AAPV-040-L2', bon_commande=bc,
                                            date_reception=datetime.date.today())
    LigneReceptionFournisseur.objects.create(reception=r, ligne_commande=lc, produit=p, quantite=10)
    with TestCase.captureOnCommitCallbacks(execute=True):
        rc = api.post(f'/api/django/stock/receptions-fournisseur/{r.id}/confirmer/', {}, format='json', **H)
    obs['confirmer_http'] = rc.status_code
    fields = {'numero': 'F-OCR-040-L2', 'date': '2026-11-02', 'fournisseur': 'Fournisseur AAPV40L2',
              'montant_ht': 10000.0, 'montant_tva': 2000.0, 'montant_ttc': 12000.0}
    with TestCase.captureOnCommitCallbacks(execute=True):
        ro = api.post('/api/django/stock/factures-fournisseur/depuis-ocr/', {'fields': fields}, format='json', **H)
    obs['ocr_http'] = ro.status_code
    obs['ocr_detail'] = None if ro.status_code < 400 else str(ro.data)[:200]
    if ro.status_code >= 400:
        print(obs)
        obs['temoin_ok'] = False
        obs['repro'] = False
        return obs
    fid = ro.data['id']
    rs = api.get('/api/django/stock/factures-fournisseur/suggestions-bcf/',
                 {'fournisseur': f.id, 'montant': ro.data.get('montant_ttc')}, **H)
    sugg = rs.data if isinstance(rs.data, list) else (rs.data or {}).get('results', [])
    obs['suggestions_http'] = rs.status_code
    obs['bcf_propose'] = bc.id in [s.get('id') for s in sugg]
    with TestCase.captureOnCommitCallbacks(execute=True):
        rp = api.patch(f'/api/django/stock/factures-fournisseur/{fid}/', {'bon_commande': bc.id}, format='json', **H)
    obs['patch_http'] = rp.status_code
    obs['patch_detail'] = None if rp.status_code < 400 else str(rp.data)[:160]
    g = api.get(f'/api/django/stock/factures-fournisseur/{fid}/', **H)
    obs['solde_du_affiche'] = str(g.data.get('solde_du'))
    obs['statut_controle'] = g.data.get('statut_controle')
    montant_ecran = g.data.get('solde_du')
    with TestCase.captureOnCommitCallbacks(execute=True):
        rpay = api.post(f'/api/django/stock/factures-fournisseur/{fid}/paiements/',
                        {'montant': float(montant_ecran), 'date_paiement': None, 'mode': 'virement'},
                        format='json', **H)
    obs['paiement_ecran_http'] = rpay.status_code
    obs['paiement_detail'] = None if rpay.status_code < 400 else str(rpay.data)[:160]
    fac = FactureFournisseur.objects.get(pk=fid)
    ac = AcompteFournisseur.objects.get(pk=ra.data['id']) if ra.status_code < 400 else None
    obs['facture_statut'] = fac.statut
    obs['total_paye'] = str(fac.total_paye)
    obs['acompte_non_consomme'] = None if ac is None else str(ac.montant_non_consomme)
    obs['decaisse_total'] = None if ac is None else str(fac.total_paye + ac.montant)
    print(obs)
    temoin_ok = (obs['acompte_http'] == 201 and obs['confirmer_http'] == 200 and obs['ocr_http'] in (200, 201))
    defaut = (obs['patch_http'] == 200 and Decimal(obs['solde_du_affiche']) == Decimal('12000')
              and rpay.status_code in (200, 201) and ac is not None
              and ac.montant_non_consomme == Decimal('3600'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
