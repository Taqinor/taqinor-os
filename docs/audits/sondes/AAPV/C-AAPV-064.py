# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K10 — deux « Générer le BC » (DA) ou deux « Commander le besoin » (chantier) concurrents créent deux BCF :
la garde est lue sans verrou (`get_object()` / `compute_besoin_materiel` hors transaction, sans
`select_for_update`). Entrelacement REJOUÉ sur une seule connexion par un crochet (jamais de threads) :
la requête 1 passe sa garde, puis — juste avant d'écrire (crochet sur `creer_bcf_depuis_lignes` /
`_creer_bcfs_groupes`) — la requête 2 s'exécute entièrement ; la requête 1 reprend ensuite. C'est l'ordre
« lecture 1, lecture 2, écriture 2, écriture 1 » de deux requêtes simultanées en READ COMMITTED.
(T) témoins : le même 2e clic SÉQUENTIEL → 409 (garde ACHT9 / bon_commande_id).
Attendu sain : 1 BCF, 2e requête 409 (relecture sous verrou)."""
SONDE = {"constat": "C-AAPV-064", "sha": "6ffa876688",
         "attendu": "repro si l'entrelacement donne 2 BCF (200+200 / 201+201) alors que le clic séquentiel est refusé 409",
         "modeles": ["installations.DemandeAchat", "installations.DemandeAchatLigne", "achats.BonCommandeFournisseur",
                     "achats.LigneBonCommandeFournisseur", "installations.Installation", "stock.Produit"]}


def sonde(ctx):
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.test import TestCase
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock import services as stock_services
    from apps.stock.models import Fournisseur, Produit, BonCommandeFournisseur
    from apps.installations.models import DemandeAchat, Installation
    from apps.installations.services import seed_reservations
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 064', slug='sonde-aapv-064')
    u = get_user_model().objects.create_user(username='sonde_aapv_064', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV64')
    p = Produit.objects.create(company=co, nom='Câble AAPV64', sku='AAPV-064', prix_vente=Decimal('50'),
                               prix_achat=Decimal('30'), quantite_stock=0, fournisseur=f)
    base = '/api/django/installations/demandes-achat/'

    def da_approuvee(objet):
        r = api.post(base, {'objet': objet, 'fournisseur_suggere': f.id}, format='json', **H)
        did = r.data['id']
        for i in (1, 2):
            api.post('/api/django/installations/demandes-achat-lignes/',
                     {'demande': did, 'produit': p.id, 'quantite': '5', 'prix_estime': '30'}, format='json', **H)
        assert api.post(f'{base}{did}/soumettre/', {}, format='json', **H).status_code == 200
        assert api.post(f'{base}{did}/approuver/', {}, format='json', **H).status_code == 200
        return did

    def nb_bcf_note(prefixe):
        return BonCommandeFournisseur.objects.filter(company=co, note__startswith=prefixe).count()

    obs = {}
    # ── A. generer-bcf ────────────────────────────────────────────────────
    dT = da_approuvee('T')
    t1 = api.post(f'{base}{dT}/generer-bcf/', {'fournisseur': f.id}, format='json', **H).status_code
    t2 = api.post(f'{base}{dT}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
    refT = DemandeAchat.objects.get(pk=dT).reference
    obs['A_temoin_sequentiel'] = {'1': t1, '2': t2.status_code, 'nb_bcf': nb_bcf_note(f'Généré depuis {refT}')}

    dR = da_approuvee('R')
    refR = DemandeAchat.objects.get(pk=dR).reference
    orig_creer = stock_services.creer_bcf_depuis_lignes
    etat = {'fait': False, 'http2': None}

    def crochet_creer(*a, **k):
        if not etat['fait']:
            etat['fait'] = True
            r2 = api.post(f'{base}{dR}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
            etat['http2'] = r2.status_code
        return orig_creer(*a, **k)

    with TestCase.captureOnCommitCallbacks(execute=True):
        with mock.patch.object(stock_services, 'creer_bcf_depuis_lignes', crochet_creer):
            r1 = api.post(f'{base}{dR}/generer-bcf/', {'fournisseur': f.id}, format='json', **H)
    daR = DemandeAchat.objects.get(pk=dR)
    bcfs_R = list(BonCommandeFournisseur.objects.filter(company=co, note=f'Généré depuis {refR}')
                  .values_list('id', 'statut'))
    obs['A_entrelace'] = {'http1': r1.status_code, 'http2': etat['http2'], 'bcfs': bcfs_R,
                          'da_statut': daR.statut, 'da_bon_commande': daR.bon_commande_id,
                          'orphelins': [b for b, _s in bcfs_R if b != daR.bon_commande_id]}

    # ── B. commander-besoin ───────────────────────────────────────────────
    bom = [{'produit_id': p.id, 'designation': p.nom, 'quantite': 10.0}]
    chT = Installation.objects.create(company=co, reference='CH-AAPV64-T', bom=bom, statut='signe')
    seed_reservations(chT)
    u1 = api.post(f'/api/django/installations/chantiers/{chT.id}/commander-besoin/', {}, format='json', **H).status_code
    u2 = api.post(f'/api/django/installations/chantiers/{chT.id}/commander-besoin/', {}, format='json', **H).status_code
    obs['B_temoin_sequentiel'] = {'1': u1, '2': u2,
                                  'nb_bcf': BonCommandeFournisseur.objects.filter(chantier_origine=chT).count()}

    chR = Installation.objects.create(company=co, reference='CH-AAPV64-R', bom=bom, statut='signe')
    seed_reservations(chR)
    orig_groupes = stock_services._creer_bcfs_groupes
    etatB = {'fait': False, 'http2': None}

    def crochet_groupes(*a, **k):
        if not etatB['fait']:
            etatB['fait'] = True
            r2 = api.post(f'/api/django/installations/chantiers/{chR.id}/commander-besoin/', {}, format='json', **H)
            etatB['http2'] = r2.status_code
        return orig_groupes(*a, **k)

    with mock.patch.object(stock_services, '_creer_bcfs_groupes', crochet_groupes):
        s1 = api.post(f'/api/django/installations/chantiers/{chR.id}/commander-besoin/', {}, format='json', **H)
    bR = BonCommandeFournisseur.objects.filter(chantier_origine=chR)
    obs['B_entrelace'] = {'http1': s1.status_code, 'http2': etatB['http2'], 'nb_bcf': bR.count(),
                          'unites': sum(l.quantite for b in bR for l in b.lignes.all())}
    print(obs)
    temoin_ok = (obs['A_temoin_sequentiel'] == {'1': 200, '2': 409, 'nb_bcf': 1}
                 and obs['B_temoin_sequentiel'] == {'1': 201, '2': 409, 'nb_bcf': 1})
    defaut_A = r1.status_code == 200 and etat['http2'] == 200 and len(bcfs_R) == 2
    defaut_B = s1.status_code == 201 and etatB['http2'] == 201 and obs['B_entrelace']['nb_bcf'] == 2
    obs['temoin_ok'] = temoin_ok
    obs['defaut_A'] = defaut_A
    obs['defaut_B'] = defaut_B
    obs['repro'] = bool(temoin_ok and (defaut_A or defaut_B))
    return obs
