# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K03 — PATCH du seul `taux_change` d'un BCF brouillon en devise : `BonCommandeFournisseurSerializer.update`
ne rejoue `apply_devise_ligne_bcf` que si `lignes` est transmis, la contre-valeur MAD des lignes reste figée
à l'ancien taux. Chaîne : POST bons-commande-fournisseur/ (EUR, taux 10,8, 10 × 100 EUR) puis PATCH
{taux_change: 20} (vraies routes). (T) témoin : PATCH taux 20 AVEC les lignes renvoyées → MAD recalculé.
Attendu sain : 2 000 MAD/u, total 20 000 dans les deux cas ; PDF « contre-valeur 20 000 »."""
SONDE = {"constat": "C-AAPV-062", "sha": "6ffa876688",
         "attendu": "repro si PATCH taux seul → 200, PU MAD 1080 et total_achat 10800 au taux 20 (témoin avec lignes : 2000 / 20000)",
         "modeles": ["achats.BonCommandeFournisseur", "achats.LigneBonCommandeFournisseur"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur, BonCommandeFournisseur
    from apps.stock.utils.pdf_fournisseur import build_bcf_context
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 062', slug='sonde-aapv-062')
    u = get_user_model().objects.create_user(username='sonde_aapv_062', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV62')
    p = Produit.objects.create(company=co, nom='Module AAPV62', sku='AAPV-062', prix_vente=Decimal('3000'),
                               prix_achat=Decimal('1000'), quantite_stock=0)
    url = '/api/django/stock/bons-commande-fournisseur/'

    def creer():
        r = api.post(url, {'fournisseur': f.id, 'devise': 'EUR', 'taux_change': '10.8',
                           'lignes': [{'produit': p.id, 'quantite': 10, 'prix_achat_unitaire': 0,
                                       'prix_achat_unitaire_devise': '100'}]}, format='json', **H)
        assert r.status_code == 201, (r.status_code, r.data)
        return r.data['id']

    def lire(bid):
        bc = BonCommandeFournisseur.objects.get(pk=bid)
        l = bc.lignes.first()
        ctxpdf = {}
        try:
            c = build_bcf_context(bc)
            ctxpdf = {'contre_valeur_mad': c.get('contre_valeur_mad'), 'taux': c.get('taux_change_affiche'),
                      'total_document': str(c.get('total_document'))}
        except Exception as exc:  # noqa
            ctxpdf = {'err': repr(exc)[:100]}
        return {'taux': str(bc.taux_change), 'pu_mad': str(l.prix_achat_unitaire),
                'pu_devise': str(l.prix_achat_unitaire_devise), 'total_achat': str(bc.total_achat), 'pdf': ctxpdf}

    # R — taux seul
    r_id = creer()
    obs = {'R_avant': lire(r_id)}
    rp = api.patch(f'{url}{r_id}/', {'taux_change': '20'}, format='json', **H)
    obs['R_patch_http'] = rp.status_code
    obs['R_apres'] = lire(r_id)
    # T — taux + lignes renvoyées (id seul)
    t_id = creer()
    lid = BonCommandeFournisseur.objects.get(pk=t_id).lignes.first().id
    tp = api.patch(f'{url}{t_id}/', {'taux_change': '20', 'lignes': [{'id': lid, 'produit': p.id, 'quantite': 10}]},
                   format='json', **H)
    obs['T_patch_http'] = tp.status_code
    obs['T_apres'] = lire(t_id)
    print(obs)
    temoin_ok = (tp.status_code == 200 and Decimal(obs['T_apres']['pu_mad']) == Decimal('2000')
                 and obs['R_avant']['pu_mad'] == '1080.00')
    defaut = (rp.status_code == 200 and Decimal(obs['R_apres']['taux']) == Decimal('20')
              and Decimal(obs['R_apres']['pu_mad']) == Decimal('1080')
              and Decimal(obs['R_apres']['total_achat']) == Decimal('10800'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
