# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K28 — séries : aucune unicité contrôlée à la saisie, et l'annulation d'une réception passe « retourné » une
série enregistrée par une AUTRE réception (`retourner_series_entrepot_reception` filtre numéro + EN_STOCK, sans
`reference_reception`).
(R) BCF 2 onduleurs ; REC-1 = 1 u. SN-100 par la vraie route `recevoir/` ; REC-2 = 1 u. saisie par erreur avec
SN-100 (même route) ; `receptions-fournisseur/<REC-2>/annuler/` (rappels on_commit exécutés) → statut de SN-100 ?
(T) témoin : REC-T = 1 u. SN-200 seule, annulée → SN-200 « retourné » (comportement voulu)."""
SONDE = {"constat": "C-AAPV-025", "sha": "b432084786",
         "attendu": "repro si R : REC-2 acceptée 200 sans alerte (1 série pour 2 unités), puis annulation -> SN-100 (de REC-1, en rayon) retourne",
         "modeles": ["stock.Produit", "stock.ReceptionFournisseur", "installations.SerieEntrepot"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, ReceptionFournisseur)
    from apps.installations.models_serie_entrepot import SerieEntrepot
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 025', slug='sonde-aapv-025')
    u = get_user_model().objects.create_user(username='sonde_aapv_025', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV25')
    urlb = '/api/django/stock/bons-commande-fournisseur/'
    p = Produit.objects.create(company=co, nom='Onduleur AAPV25', sku='AAPV-025', prix_vente=Decimal('9000'),
                               quantite_stock=0)
    bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-AAPV-025',
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=3,
                                                    prix_achat_unitaire=Decimal('7000'))

    def recevoir(serie):
        avant = set(ReceptionFournisseur.objects.filter(bon_commande=bc).values_list('id', flat=True))
        r = api.post(f'{urlb}{bc.id}/recevoir/', {'receptions': [{'ligne': lc.id, 'quantite': 1,
                                                                   'numeros_serie': [serie]}]}, format='json', **H)
        rec = ReceptionFournisseur.objects.filter(bon_commande=bc).exclude(id__in=avant).first()
        return r.status_code, (None if r.status_code < 400 else str(r.data)[:160]), rec

    def series():
        return list(SerieEntrepot.objects.filter(company=co, produit=p).order_by('numero_serie').values_list(
            'numero_serie', 'statut', 'reference_reception'))

    c1, d1, rec1 = recevoir('SN-100')
    c2, d2, rec2 = recevoir('SN-100')
    p.refresh_from_db()
    avant = {'stock': p.quantite_stock, 'series': series()}
    with TestCase.captureOnCommitCallbacks(execute=True):
        ra = api.post(f'/api/django/stock/receptions-fournisseur/{rec2.id}/annuler/', {}, format='json', **H)
    p.refresh_from_db()
    obs = {'R': {'rec1': (c1, d1, rec1.reference), 'rec2': (c2, d2, rec2.reference), 'avant_annulation': avant,
                 'annuler_rec2': ra.status_code, 'stock_final': p.quantite_stock, 'series_finales': series()}}
    cT, dT, recT = recevoir('SN-200')
    with TestCase.captureOnCommitCallbacks(execute=True):
        raT = api.post(f'/api/django/stock/receptions-fournisseur/{recT.id}/annuler/', {}, format='json', **H)
    obs['T'] = {'recT': (cT, recT.reference), 'annuler': raT.status_code, 'series': series()}
    print(obs)
    r, t = obs['R'], obs['T']
    sn200 = [s for s in t['series'] if s[0] == 'SN-200']
    temoin_ok = raT.status_code == 200 and sn200 and sn200[0][1] == 'retourne'
    sn100_avant = [s for s in r['avant_annulation']['series'] if s[0] == 'SN-100']
    sn100 = [s for s in r['series_finales'] if s[0] == 'SN-100']
    defaut = (c2 == 200 and r['avant_annulation']['stock'] == 2 and len(sn100_avant) == 1
              and sn100_avant[0][2] == rec1.reference and ra.status_code == 200
              and r['stock_final'] == 1 and sn100 and sn100[0][1] == 'retourne')
    obs['temoin_ok'] = bool(temoin_ok)
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
