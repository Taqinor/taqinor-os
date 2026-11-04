SONDE = {"constat": "C-ASTK-VER4-001", "sha": "c38868a62",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.InventaireSession",
                     "stock.RevalorisationStock", "stock.RetourFournisseur",
                     "stock.ModeleBonCommandeFournisseur", "stock.BonCommandeFournisseur",
                     "stock.ConditionnementProduit", "stock.DepotConsignation"],
         "attendu": "non-régression ASTK1-8 sur main c38868a62 : garde de classe vide ; id de B = id absent "
                    "(statut + corps identiques) sur inventaire, revalo PATCH, retour (BCF B), modèle BCF "
                    "(fournisseur B, lignes produit B), conditionnement, rappel, incident qualité, RFA, BCF acheteur B ; "
                    "nouveau_cout figé ; coût moyen de PB inchangé = celui de son propre BCF B (77, achats), jamais un coût posé par A ; generer ignore une ligne héritée PB ; "
                    "décrément d'expédition refuse une ligne PB ; consignation client B refusée ; stock PB inchangé"}


def sonde(ctx):
    import re
    from decimal import Decimal
    from rest_framework.test import APIClient, APIRequestFactory
    from rest_framework.request import Request
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import (
        Fournisseur, Produit, MouvementStock, BonCommandeFournisseur,
        LigneBonCommandeFournisseur, ModeleBonCommandeFournisseur,
        ModeleBonCommandeFournisseurLigne, RevalorisationStock, DepotConsignation,
    )
    from apps.stock import test_astk_garde_fk_societe as garde
    from apps.stock import services as S
    U = get_user_model()
    perms = dict(CANONICAL_SYSTEM_ROLES)
    a = Company.objects.create(nom='SONDE-VER4-A', slug='sonde-astk-ver4-a')
    b = Company.objects.create(nom='SONDE-VER4-B', slug='sonde-astk-ver4-b')
    role = Role.objects.create(company=a, nom='Administrateur',
                               permissions=list(perms['Administrateur']), est_systeme=True)
    ua = U.objects.create_user(username='sonde-astk-ver4-a', password='x', company=a, role=role)
    ub = U.objects.create_user(username='sonde-astk-ver4-b', password='x', company=b,
                               role_legacy='responsable')
    fa = Fournisseur.objects.create(company=a, nom='F-A-VER4')
    fb = Fournisseur.objects.create(company=b, nom='FOURNISSEUR-B-SECRET')
    pa = Produit.objects.create(company=a, nom='PA-VER4', sku='PA-VER4', prix_achat=Decimal('10'),
                                prix_vente=Decimal('20'), quantite_stock=10)
    pb = Produit.objects.create(company=b, nom='PB-SECRET-VER4', sku='PB-VER4', prix_achat=Decimal('50'),
                                prix_vente=Decimal('80'), quantite_stock=100)
    bcb = BonCommandeFournisseur.objects.create(company=b, reference='BCF-B-SECRET-VER4', fournisseur=fb,
                                                statut=BonCommandeFournisseur.Statut.RECU)
    LigneBonCommandeFournisseur.objects.create(bon_commande=bcb, produit=pb, quantite=20,
                                               quantite_recue=20, prix_achat_unitaire=Decimal('77'))
    res = {}
    echecs = []

    # 1. ASTK8 — garde de classe rejouée.
    req = Request(APIRequestFactory().get('/'))
    req.user = ua
    classes = garde.decouvrir_serializers()
    manquants = []
    for c in classes:
        manquants.extend(garde.champs_non_bornes(c, req, a, b))
    res['garde'] = f'{len(classes)} serializers, non bornés={manquants}'
    if manquants or len(classes) < 40:
        echecs.append('garde')

    api = APIClient(); api.force_authenticate(ua)
    H = {'HTTP_HOST': 'localhost'}
    rid = lambda t: re.sub(r'"request_id":\s*"[^"]*"', '"request_id":"X"', t)

    def paire(nom, methode, url, corps_b, corps_x, idb):
        r1 = getattr(api, methode)(url, corps_b, format='json', **H)
        r2 = getattr(api, methode)(url, corps_x, format='json', **H)
        c1 = rid(r1.content.decode()).replace(str(idb), 'ID')
        c2 = rid(r2.content.decode()).replace('99999999', 'ID')
        ok = (r1.status_code == r2.status_code and r1.status_code in (400, 404)
              and c1 == c2 and 'SECRET' not in c1)
        res[nom] = f'{r1.status_code}/{r2.status_code} identiques={c1 == c2} corps={c1[:160]}'
        if not ok:
            echecs.append(nom)

    P = '/api/django/stock/'
    # ASTK1
    paire('astk1_inventaire', 'post', P + 'inventaire-sessions/',
          {'motif': 'x', 'lignes': [{'produit': pb.id, 'quantite_comptee': 0}]},
          {'motif': 'x', 'lignes': [{'produit': 99999999, 'quantite_comptee': 0}]}, pb.id)
    revalo = S.creer_revalorisation(company=a, produit=pa, nouveau_cout=Decimal('12'), motif='m', user=ua) \
        if hasattr(S, 'creer_revalorisation') else None
    if revalo is not None:
        paire('astk1_revalo_patch_produit', 'patch', f'{P}revalorisations-stock/{revalo.id}/',
              {'produit': pb.id}, {'produit': 99999999}, pb.id)
        rn = api.patch(f'{P}revalorisations-stock/{revalo.id}/', {'nouveau_cout': '1'}, format='json', **H)
        revalo.refresh_from_db()
        res['astk1_nouveau_cout_fige'] = f'{rn.status_code} relu={revalo.nouveau_cout} produit={revalo.produit_id == pa.id}'
        if rn.status_code < 400 or revalo.nouveau_cout != Decimal('12') or revalo.produit_id != pa.id:
            echecs.append('astk1_nouveau_cout_fige')
    else:
        echecs.append('creer_revalorisation absent')
    cout = S.average_cost_with_source(pb)
    res['astk1_cout_pb'] = str(cout)
    # ASTK2
    paire('astk2_retour_bcf_b', 'post', P + 'retours-fournisseur/',
          {'fournisseur': fa.id, 'bon_commande': bcb.id, 'lignes': [{'produit': pa.id, 'quantite': 1}]},
          {'fournisseur': fa.id, 'bon_commande': 99999999, 'lignes': [{'produit': pa.id, 'quantite': 1}]}, bcb.id)
    paire('astk2_modele_fournisseur_b', 'post', P + 'modeles-bcf/',
          {'nom': 'M', 'fournisseur': fb.id}, {'nom': 'M', 'fournisseur': 99999999}, fb.id)
    paire('astk2_modele_ligne_pb', 'post', P + 'modeles-bcf/',
          {'nom': 'M', 'fournisseur': fa.id, 'lignes': [{'produit': pb.id, 'quantite': 3}]},
          {'nom': 'M', 'fournisseur': fa.id, 'lignes': [{'produit': 99999999, 'quantite': 3}]}, pb.id)
    modele = ModeleBonCommandeFournisseur.objects.create(company=a, nom='M-herite', fournisseur=fa)
    ModeleBonCommandeFournisseurLigne.objects.create(modele=modele, produit=pa, quantite=1)
    ModeleBonCommandeFournisseurLigne.objects.create(modele=modele, produit=pb, quantite=3)
    rg = api.post(f'{P}modeles-bcf/{modele.id}/generer/', {}, format='json', **H)
    gen_txt = rg.content.decode()
    nouveaux = BonCommandeFournisseur.objects.filter(company=a, note__contains='M-herite')
    lignes_pb = LigneBonCommandeFournisseur.objects.filter(bon_commande__in=nouveaux, produit=pb).count()
    res['astk2_generer'] = f'{rg.status_code} lignes_pb={lignes_pb} secret_dans_corps={"SECRET" in gen_txt}'
    if lignes_pb or 'SECRET' in gen_txt:
        echecs.append('astk2_generer')
    # ASTK4
    paire('astk4_bcf_acheteur_b', 'post', P + 'bons-commande-fournisseur/',
          {'fournisseur': fa.id, 'acheteur': ub.id}, {'fournisseur': fa.id, 'acheteur': 99999999}, ub.id)
    # ASTK5
    paire('astk5_conditionnement_pb', 'post', P + 'conditionnements/',
          {'produit': pb.id, 'code': 'T', 'libelle': 'Touret', 'quantite': 10},
          {'produit': 99999999, 'code': 'T', 'libelle': 'Touret', 'quantite': 10}, pb.id)
    # ASTK6
    paire('astk6_rappel_pb', 'post', P + 'alertes-rappel/',
          {'produit': pb.id, 'motif': 'Defaut'}, {'produit': 99999999, 'motif': 'Defaut'}, pb.id)
    # ASTK7
    paire('astk7_incident_fb', 'post', P + 'incidents-qualite-fournisseur/',
          {'fournisseur': fb.id, 'titre': 'x', 'description': 'x'},
          {'fournisseur': 99999999, 'titre': 'x', 'description': 'x'}, fb.id)
    paire('astk7_rfa_fb', 'post', P + 'accords-rfa-fournisseur/',
          {'fournisseur': fb.id, 'nom': 'x'}, {'fournisseur': 99999999, 'nom': 'x'}, fb.id)
    from apps.stock import services_consignation as SC
    modele_client = DepotConsignation._meta.get_field('client').related_model
    cb = modele_client.objects.create(company=b, nom='CLIENT-B-SECRET')
    import datetime
    msgs = []
    for cid in (cb.id, 99999999):
        try:
            SC.creer_depot_consignation(company=a, user=ua, client_id=cid, produit_id=pa.id, quantite=1,
                                        date_depot=datetime.date.today())
            msgs.append('ACCEPTE')
        except Exception as e:  # noqa
            msgs.append(f'{type(e).__name__}:{e}')
    res['astk7_consignation_client_b'] = msgs
    if msgs[0] != msgs[1]:
        echecs.append('astk7_consignation')
    # ASTK3 — ligne de PB injectée dans une unité de A, décrément d'expédition.
    from apps.stock import services_wms as W
    from apps.stock.models_wms import UniteLogistique, UniteLogistiqueLigne
    u2 = W.creer_unite_logistique(company=a)
    UniteLogistiqueLigne.objects.create(company=a, unite=u2, produit=pb, quantite=3)
    UniteLogistique.objects.filter(pk=u2.pk).update(statut=UniteLogistique.Statut.SCELLE)
    u2.refresh_from_db()
    exp = W.creer_expedition_transporteur(company=a, unite=u2)
    try:
        W.decrementer_stock_expedition(expedition=exp, user=ua)
        dec = 'ACCEPTE'
    except Exception as e:  # noqa
        dec = f'{type(e).__name__}:{e}'
    res['astk3_decrement'] = dec
    if dec == 'ACCEPTE':
        echecs.append('astk3_decrement')

    pb.refresh_from_db()
    mvt_pb = MouvementStock.objects.filter(produit=pb).count()
    cout2 = S.average_cost_with_source(pb)
    res['persistance_pb'] = f'stock={pb.quantite_stock} mouvements={mvt_pb} cout={cout2}'
    if pb.quantite_stock != 100 or mvt_pb != 0 or cout2 != cout or cout2[1] != 'achats':
        echecs.append('persistance_pb')
    for k, v in res.items():
        print(f'{k}: {v}')
    print('ECHECS =', echecs)
    return {'repro': bool(echecs), 'echecs': echecs}
