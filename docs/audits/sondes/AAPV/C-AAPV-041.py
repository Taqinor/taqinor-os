# flake8: noqa  (sonde parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K41 — le rapprochement 3 voies ne compare que le HT cumulé au reçu × PU ; rien ne vérifie HT + TVA = TTC.
BCF 10 × 1 000 HT, réception de 5 confirmée (attendu 5 000 HT). (R1) facture OCR réelle
(`creer_facture_fournisseur_depuis_ocr`) où seul le TTC 12 000 est lu (HT 0) puis PATCH {bon_commande} ;
(R2) saisie API HT 1 000 / TVA 200 / TTC 12 000 puis PATCH. On paie ensuite 12 000.
(T) témoin : HT 12 000 / TTC 14 400 lié par PATCH → exception (le 3 voies marche quand le HT dépasse).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AAPV-041", "sha": "5f603acce",
         "attendu": "repro si R1 et R2 restent « normale » et le paiement 12000 passe (201) pour 6000 TTC reçus ; T : exception",
         "modeles": ["achats.FactureFournisseur", "achats.PaiementFournisseur", "achats.ReceptionFournisseur"]}

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
    from apps.stock.services import creer_facture_fournisseur_depuis_ocr
    co, u, api, f, p = _base('aapv-041')
    obs = {}

    def lier_et_payer(fid, bc, cle):
        rp = api.patch(f'/api/django/stock/factures-fournisseur/{fid}/', {'bon_commande': bc.id}, format='json', **H)
        fac = FactureFournisseur.objects.get(pk=fid)
        obs[cle] = {'patch': rp.status_code, 'ht': str(fac.montant_ht), 'tva': str(fac.montant_tva),
                    'ttc': str(fac.montant_ttc), 'statut_controle': fac.statut_controle,
                    'solde_du': str(fac.solde_du)}
        rpay = api.post('/api/django/stock/paiements-fournisseur/',
                        {'facture': fid, 'montant': str(fac.solde_du), 'date_paiement': '2026-11-03',
                         'mode': 'virement'}, format='json', **H)
        obs[cle]['paiement_http'] = rpay.status_code
        obs[cle]['paiement_detail'] = None if rpay.status_code < 400 else str(rpay.data)[:140]

    # R1 — OCR : TTC lu seul.
    b1, l1 = _bcf(co, f, p, 'BCF-AAPV-041-R1')
    _recevoir(api, co, b1, l1, 5, 'REC-AAPV-041-R1')
    fac1, _d = creer_facture_fournisseur_depuis_ocr(company=co, user=u,
                                                    fields={'fournisseur': f.nom, 'numero': 'OCR-041-1',
                                                            'montant_ttc': '12000'})
    lier_et_payer(fac1.id, b1, 'R1_ocr_ttc_seul')
    # R2 — saisie API HT incohérent.
    b2, l2 = _bcf(co, f, p, 'BCF-AAPV-041-R2')
    _recevoir(api, co, b2, l2, 5, 'REC-AAPV-041-R2')
    r2 = api.post('/api/django/stock/factures-fournisseur/',
                  {'fournisseur': f.id, 'ref_fournisseur': 'F-041-2', 'date_facture': '2026-11-02',
                   'montant_ht': '1000.00', 'montant_tva': '200.00', 'montant_ttc': '12000.00'}, format='json', **H)
    obs['R2_creation_http'] = r2.status_code
    lier_et_payer(r2.data['id'], b2, 'R2_ht_1000_ttc_12000')
    # T — témoin : HT au-dessus du reçu.
    b3, l3 = _bcf(co, f, p, 'BCF-AAPV-041-T')
    _recevoir(api, co, b3, l3, 5, 'REC-AAPV-041-T')
    r3 = api.post('/api/django/stock/factures-fournisseur/',
                  {'fournisseur': f.id, 'ref_fournisseur': 'F-041-3', 'date_facture': '2026-11-02',
                   'montant_ht': '12000.00', 'montant_tva': '2400.00', 'montant_ttc': '14400.00'}, format='json', **H)
    rp3 = api.patch(f'/api/django/stock/factures-fournisseur/{r3.data["id"]}/', {'bon_commande': b3.id},
                    format='json', **H)
    obs['T_statut_controle'] = FactureFournisseur.objects.get(pk=r3.data['id']).statut_controle
    obs['recu_ttc_attendu'] = '6000.00'
    print(obs)
    temoin_ok = obs['T_statut_controle'] == 'exception'
    defaut = all(obs[k]['statut_controle'] == 'normale' and obs[k]['paiement_http'] == 201
                 for k in ('R1_ocr_ttc_seul', 'R2_ht_1000_ttc_12000'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
