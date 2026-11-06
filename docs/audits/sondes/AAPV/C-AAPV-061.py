# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K02 — « Commander le besoin » route la ligne chez le fournisseur au tarif PrixFournisseur le plus bas
(`cheapest_prix_fournisseur`, sans `est_en_vigueur`) mais pose le prix CATALOGUE `produit.prix_achat`.
Chaîne : P prix_achat 1 400 ; tarif F2 1 150 en vigueur ; tarif F3 900 expiré hier ; chantier en manque 10 ;
vraie route POST chantiers/<id>/commander-besoin/ {}. Lecteur de référence : `prix_effectif_fournisseur`.
Attendu sain : BCF chez F2 à 1 150 (11 500)."""
SONDE = {"constat": "C-AAPV-061", "sha": "6ffa876688",
         "attendu": "repro si BCF chez F3 (tarif expiré) et PU 1400 (prix catalogue) au lieu de F2 à 1150",
         "modeles": ["stock.Produit", "achats.BonCommandeFournisseur", "achats.LigneBonCommandeFournisseur",
                     "achats.PrixFournisseur", "installations.Installation"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation
    from apps.installations.services import seed_reservations
    from apps.stock.models import Produit, Fournisseur, PrixFournisseur, LigneBonCommandeFournisseur
    from apps.stock.services import prix_effectif_fournisseur
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 061', slug='sonde-aapv-061')
    u = get_user_model().objects.create_user(username='sonde_aapv_061', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f2 = Fournisseur.objects.create(company=co, nom='F2-AAPV61')
    f3 = Fournisseur.objects.create(company=co, nom='F3-AAPV61')
    p = Produit.objects.create(company=co, nom='Onduleur AAPV61', sku='AAPV-061', prix_vente=Decimal('2000'),
                               prix_achat=Decimal('1400'), quantite_stock=0)
    hier = datetime.date.today() - datetime.timedelta(days=1)
    PrixFournisseur.objects.create(company=co, produit=p, fournisseur=f2, prix_achat=Decimal('1150'))
    PrixFournisseur.objects.create(company=co, produit=p, fournisseur=f3, prix_achat=Decimal('900'),
                                   date_debut=hier - datetime.timedelta(days=60), date_fin=hier)
    ch = Installation.objects.create(company=co, reference='CH-AAPV61', statut='signe',
                                     bom=[{'produit_id': p.id, 'designation': p.nom, 'quantite': 10.0}])
    seed_reservations(ch)
    ref = {'effectif_F2': str(prix_effectif_fournisseur(p, f2, quantite=10)),
           'effectif_F3': str(prix_effectif_fournisseur(p, f3, quantite=10))}
    r = api.post(f'/api/django/installations/chantiers/{ch.id}/commander-besoin/', {}, format='json', **H)
    lignes = list(LigneBonCommandeFournisseur.objects.filter(bon_commande__company=co, produit=p)
                  .select_related('bon_commande__fournisseur'))
    obs = {'reference': ref, 'http': r.status_code,
           'detail': None if r.status_code < 400 else str(r.data)[:140],
           'lignes': [{'fournisseur': l.bon_commande.fournisseur.nom, 'quantite': l.quantite,
                       'pu': str(l.prix_achat_unitaire),
                       'total': str(l.quantite * l.prix_achat_unitaire)} for l in lignes]}
    print(obs)
    temoin_ok = ref['effectif_F2'] == '1150.00' and ref['effectif_F3'] == 'None'
    defaut = (r.status_code == 201 and len(lignes) == 1 and lignes[0].bon_commande.fournisseur_id == f3.id
              and lignes[0].prix_achat_unitaire == Decimal('1400'))
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
