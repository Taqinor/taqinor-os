# flake8: noqa  (seconde lentille PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §B.5)
"""K02 / seconde lentille — chemin RÉEL de l'écran, rôle responsable, AUCUN tarif expiré.
La sonde d'origine (C-AAPV-061) exigeait un tarif expiré moins cher. Angle ici : un seul tarif, EN VIGUEUR,
F2 à 1 150 (P catalogue 1 400) — cas courant. Geste écran : ChantierApprovisionnement.jsx::commander envoie
{produits: [<ids en manque>]} ; puis BonsCommandeFournisseur.jsx::envoyer fait PATCH du brouillon (buildPayload,
lignes renvoyées avec leur id) puis POST envoyer/. On regarde si quelque chose signale le prix catalogue.
Attendu sain : BCF chez F2 à 1 150 (11 500) — ou au moins un `prix_warnings` sur le PATCH / l'envoi."""
SONDE = {"constat": "C-AAPV-061", "sha": "ff075ef7d4",
         "attendu": "elargi si BCF chez F2 (tarif en vigueur) mais PU 1400 catalogue, et ni PATCH ni envoyer ne signalent rien",
         "modeles": ["stock.Produit", "achats.BonCommandeFournisseur", "achats.LigneBonCommandeFournisseur",
                     "achats.PrixFournisseur", "installations.Installation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation
    from apps.installations.services import seed_reservations
    from apps.stock.models import (Produit, Fournisseur, PrixFournisseur, LigneBonCommandeFournisseur,
                                   BonCommandeFournisseur)
    from apps.stock.services import prix_effectif_fournisseur
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 061 L2', slug='sonde-aapv-061-l2')
    u = get_user_model().objects.create_user(username='sonde_aapv_061_l2', password='x',
                                             role_legacy='responsable', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f2 = Fournisseur.objects.create(company=co, nom='F2-AAPV61L2')
    p = Produit.objects.create(company=co, nom='Onduleur AAPV61L2', sku='AAPV-061-L2', prix_vente=Decimal('2000'),
                               prix_achat=Decimal('1400'), quantite_stock=0)
    PrixFournisseur.objects.create(company=co, produit=p, fournisseur=f2, prix_achat=Decimal('1150'))
    ch = Installation.objects.create(company=co, reference='CH-AAPV61L2', statut='signe',
                                     bom=[{'produit_id': p.id, 'designation': p.nom, 'quantite': 10.0}])
    seed_reservations(ch)
    effectif = prix_effectif_fournisseur(p, f2, quantite=10)
    with TestCase.captureOnCommitCallbacks(execute=True):
        r = api.post(f'/api/django/installations/chantiers/{ch.id}/commander-besoin/',
                     {'produits': [p.id]}, format='json', **H)
    obs = {'role': 'responsable', 'effectif_F2': str(effectif), 'commander_http': r.status_code,
           'detail': None if r.status_code < 400 else str(r.data)[:160]}
    lignes = list(LigneBonCommandeFournisseur.objects.filter(bon_commande__company=co, produit=p)
                  .select_related('bon_commande__fournisseur'))
    obs['lignes'] = [{'fournisseur': l.bon_commande.fournisseur.nom, 'quantite': l.quantite,
                      'pu': str(l.prix_achat_unitaire)} for l in lignes]
    patch_http = env_http = None
    warnings_patch = warnings_env = None
    bc_statut = None
    if len(lignes) == 1:
        bc = lignes[0].bon_commande
        g = api.get(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/', **H)
        obs['get_http'] = g.status_code
        obs['get_a_prix_warnings'] = 'prix_warnings' in (g.data or {})
        payload = {'fournisseur': f2.id, 'date_commande': None, 'date_livraison_prevue': None, 'note': None,
                   'acheteur': None, 'ref_fournisseur': None, 'note_bas_page': None, 'incoterm': None,
                   'lignes': [{'id': l['id'], 'produit': l['produit'], 'designation': '',
                               'quantite': l['quantite'], 'prix_achat_unitaire': l['prix_achat_unitaire']}
                              for l in g.data['lignes']]}
        rp = api.patch(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/', payload, format='json', **H)
        patch_http = rp.status_code
        warnings_patch = (rp.data or {}).get('prix_warnings') if rp.status_code < 400 else str(rp.data)[:160]
        with TestCase.captureOnCommitCallbacks(execute=True):
            re_ = api.post(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/envoyer/', {}, format='json', **H)
        env_http = re_.status_code
        warnings_env = (re_.data or {}).get('prix_warnings') if re_.status_code < 400 else str(re_.data)[:160]
        bc.refresh_from_db()
        bc_statut = bc.statut
        lignes[0].refresh_from_db()
        obs['pu_apres_envoi'] = str(lignes[0].prix_achat_unitaire)
    obs.update({'patch_http': patch_http, 'prix_warnings_patch': warnings_patch,
                'envoyer_http': env_http, 'prix_warnings_envoyer': warnings_env, 'bcf_statut': bc_statut})
    print(obs)
    temoin_ok = obs['effectif_F2'] == '1150.00'
    defaut = (r.status_code == 201 and len(lignes) == 1 and lignes[0].bon_commande.fournisseur_id == f2.id
              and obs.get('pu_apres_envoi') == '1400.00' and not warnings_patch and env_http == 200
              and bc_statut == BonCommandeFournisseur.Statut.ENVOYE)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    return obs
