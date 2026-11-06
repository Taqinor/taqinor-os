# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K01 — le besoin matériel retranche du stock les réservations des AUTRES chantiers sans les plafonner au
stock : deux chantiers qui réservent chacun 10 P pour un stock de 10 se voient tous deux « disponible 0,
manque 10 ». Chaîne : P stock 10, chantiers A et B (nomenclature gelée 10 P), `seed_reservations` sur les deux,
vraies routes GET chantiers/<id>/besoin-materiel/ puis POST chantiers/<id>/commander-besoin/ sur A et B.
(T) témoin : A seul réservé → manque 0 (le stock le couvre). Attendu sain : 10 commandés au total (20 requis −
10 en stock)."""
SONDE = {"constat": "C-AAPV-060", "sha": "6ffa876688",
         "attendu": "repro si A et B affichent chacun manque 10 et commander-besoin crée 20 unités au total (besoin net 10)",
         "modeles": ["stock.Produit", "achats.BonCommandeFournisseur", "achats.LigneBonCommandeFournisseur",
                     "installations.Installation", "installations.StockReservation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation
    from apps.installations.services import seed_reservations
    from apps.stock.models import Produit, Fournisseur, LigneBonCommandeFournisseur
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 060', slug='sonde-aapv-060')
    u = get_user_model().objects.create_user(username='sonde_aapv_060', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV60')
    p = Produit.objects.create(company=co, nom='Panneau AAPV60', sku='AAPV-060', prix_vente=Decimal('200'),
                               prix_achat=Decimal('100'), quantite_stock=10, fournisseur=f)
    bom = [{'produit_id': p.id, 'designation': p.nom, 'quantite': 10.0}]
    a = Installation.objects.create(company=co, reference='CH-AAPV60-A', bom=bom, statut='signe')
    seed_reservations(a)

    def besoin(inst):
        r = api.get(f'/api/django/installations/chantiers/{inst.id}/besoin-materiel/', **H)
        it = (r.data.get('items') or [{}])[0] if r.status_code == 200 else {}
        return {'http': r.status_code, 'disponible': it.get('disponible'), 'reserve': it.get('reserve'),
                'manque': it.get('manque')}

    obs = {'temoin_A_seul': besoin(a)}
    b = Installation.objects.create(company=co, reference='CH-AAPV60-B', bom=bom, statut='signe')
    seed_reservations(b)
    obs['A_avec_B'] = besoin(a)
    obs['B'] = besoin(b)
    cmd = {}
    for nom, inst in (('A', a), ('B', b)):
        r = api.post(f'/api/django/installations/chantiers/{inst.id}/commander-besoin/', {}, format='json', **H)
        cmd[nom] = {'http': r.status_code,
                    'detail': None if r.status_code < 400 else str(r.data)[:140]}
    obs['commander_besoin'] = cmd
    lignes = LigneBonCommandeFournisseur.objects.filter(bon_commande__company=co, produit=p)
    obs['unites_commandees'] = sum(l.quantite for l in lignes)
    obs['nb_bcf'] = lignes.values('bon_commande').distinct().count()
    p.refresh_from_db()
    obs['stock'] = p.quantite_stock
    # Variante stock 0 : le disponible devient NÉGATIF (0 − 10 réservés par l'autre) et gonfle le manque au-delà
    # du requis (manque = requis + réservé des autres).
    q = Produit.objects.create(company=co, nom='Onduleur AAPV60', sku='AAPV-060Q', prix_vente=Decimal('900'),
                               prix_achat=Decimal('500'), quantite_stock=0, fournisseur=f)
    bomq = [{'produit_id': q.id, 'designation': q.nom, 'quantite': 10.0}]
    c = Installation.objects.create(company=co, reference='CH-AAPV60-C', bom=bomq, statut='signe')
    d = Installation.objects.create(company=co, reference='CH-AAPV60-D', bom=bomq, statut='signe')
    seed_reservations(c)
    seed_reservations(d)
    obs['stock0_C'] = besoin(c)
    obs['stock0_D'] = besoin(d)
    print(obs)
    temoin_ok = obs['temoin_A_seul']['http'] == 200 and obs['temoin_A_seul']['manque'] == 0
    defaut = (obs['A_avec_B']['manque'] == 10 and obs['B']['manque'] == 10 and obs['unites_commandees'] == 20)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
