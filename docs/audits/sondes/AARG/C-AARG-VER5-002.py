# flake8: noqa  (sonde de contre-visite de clôture PA4 « Argent », rejouable par scripts/sonde.py — METHODE §C.4)
"""VER5 AARG2/AUD127 : restauration sans garde. Devis accepté → BC1 (vraie API) → creer-facture → F1 émise ;
`annuler_facture(F1)` (sans argent → avoir miroir A1) ; `POST bons-commande/<BC1>/creer-facture/` → F2 (AARG30
détache F1 du BC) → émise ; puis `POST avoirs/<A1>/annuler/` (`AvoirViewSet.annuler` restaure F1 à son ancien
statut sans regarder si la vente a été refacturée). Lecture : factures vivantes de la vente, Σ montant_du vs TTC
du devis, lien BC1. Fonctions réelles + vraies routes ; transaction annulée."""
SONDE = {"constat": "C-AARG-002", "sha": "2781a2049",
         "attendu": "repro si l'annulation de A1 rend 200 et laisse 2 factures vivantes (F1 restaurée + F2) dont Σ dû = 2 × TTC ; sain : 400/409 tant que F2 vit",
         "modeles": ["ventes.Devis", "ventes.BonCommande", "ventes.Facture", "ventes.Avoir", "ventes.LigneFacture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture, Avoir
    from apps.ventes.domain.annulation_facture import annuler_facture
    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/ventes'
    co = Company.objects.create(nom='Sonde VER5 002', slug='sonde-ver5-002')
    u = get_user_model().objects.create_user(username='sonde_ver5_002', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='V502', email='v502@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit V502', sku='SONDE-V502', prix_vente=Decimal('1000'), quantite_stock=50)
    d = Devis.objects.create(company=co, reference='DEV-V502', client=cl, statut='accepte', taux_tva=Decimal('20'),
                             created_by=u)
    LigneDevis.objects.create(devis=d, produit=p, designation='Centrale V502', quantite=Decimal('1'),
                              prix_unitaire=Decimal('1000'))
    e = {}

    def st(r):
        return [r.status_code, None if r.status_code < 400 else str(getattr(r, 'data', ''))[:160]]

    r = api.post(B + '/bons-commande/', {'client': cl.pk, 'devis': d.pk}, format='json', **H)
    e['creer_bc'] = st(r)
    if r.status_code != 201:
        return {'repro': False, 'etapes': e}
    bc_id = r.data['id']
    e['confirmer'] = st(api.post(f'{B}/bons-commande/{bc_id}/confirmer/', {}, format='json', **H))
    r = api.post(f'{B}/bons-commande/{bc_id}/creer-facture/', {}, format='json', **H)
    e['creer_F1'] = st(r)
    if r.status_code != 201:
        return {'repro': False, 'etapes': e}
    f1 = r.data['id']
    e['emettre_F1'] = st(api.post(f'{B}/factures/{f1}/emettre/', {}, format='json', **H))
    F1 = Facture.objects.get(pk=f1)
    e['F1_apres_emission'] = [F1.reference, F1.statut, str(F1.total_ttc), str(F1.montant_du)]
    F1 = annuler_facture(F1, user=u, directive=None)
    a1 = F1.avoir_annulation
    F1 = Facture.objects.get(pk=f1)
    e['F1_apres_annulation'] = [F1.statut, a1.reference if a1 else None, str(a1.total_ttc) if a1 else None]
    if a1 is None:
        return {'repro': False, 'etapes': e}
    r = api.post(f'{B}/bons-commande/{bc_id}/creer-facture/', {}, format='json', **H)
    e['creer_F2'] = st(r)
    if r.status_code != 201:
        return {'repro': False, 'etapes': e}
    f2 = r.data['id']
    e['emettre_F2'] = st(api.post(f'{B}/factures/{f2}/emettre/', {}, format='json', **H))
    r = api.post(f'{B}/avoirs/{a1.id}/annuler/', {}, format='json', **H)
    e['annuler_A1'] = st(r)
    vivantes = list(Facture.objects.filter(company=co, devis=d).exclude(statut=Facture.Statut.ANNULEE))
    du = sum((f.montant_du for f in vivantes), Decimal('0'))
    ttc_vente = Facture.objects.get(pk=f2).total_ttc
    obs = {'etapes': e,
           'vivantes': [[f.pk == f1 and 'F1' or 'F2', f.reference, f.statut, str(f.total_ttc), str(f.montant_du),
                         f.bon_commande_id] for f in vivantes],
           'somme_du': str(du), 'ttc_vente': str(ttc_vente), 'bc1': bc_id,
           'A1_statut': Avoir.objects.get(pk=a1.pk).statut}
    print(obs)
    obs['repro'] = bool(r.status_code == 200 and len(vivantes) == 2 and du >= 2 * ttc_vente > 0)
    return obs
