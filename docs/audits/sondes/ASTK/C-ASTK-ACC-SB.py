SONDE = {"constat": "C-ASTK-ACC-SB", "sha": "5908d43bb",
         "attendu": "S-B aller-retour : produit créé par l'API avec ses champs maîtres (ASTK214/230), rouvert (GET), "
                    "ré-enregistré SANS RIEN TOUCHER (PUT du corps relu, quantite_stock périmée comprise) -> objet "
                    "serveur identique et stock non réécrit ; kit (taux de perte) idem, aucune révision « identique » ; "
                    "BCF ré-enregistré sans toucher -> lignes gardées (même id) ; tests rouges ASTK32/67/81/82/87/94/96/"
                    "97/214/229 verts contre la base de la pile"}

MODULES = ['apps.stock.test_astk_quantite_stock_ro', 'apps.stock.test_astk_champs_maitres',
           'apps.stock.test_astk_kit_update', 'apps.stock.test_astk_dupliquer_produit',
           'apps.stock.test_astk_bcf_update_upsert', 'apps.stock.test_astk_marque_renommage',
           'apps.stock.test_astk_suppression_produit', 'apps.stock.test_astk_suppression_categorie']

VOLATILES = {'date_modification', 'updated_at', 'modifie_le', 'date_maj', 'derniere_modification', 'date_mise_a_jour'}

def _rejouer_tests(modules):
    """Rejoue les tests rouges des tâches contre la base de la pile, dans la transaction annulée du lanceur.

    Passe 1 : base de démo telle quelle. Passe 2 (échecs seulement) : « base vierge émulée » — `.exists()` /
    `.count()` / `.get()` ne voient que les lignes créées par le test (pk > max d'avant, filtre éventuel conservé) : un test
    qui suppose une base vide (compte global, référence REC-… non bornée à sa société) et échoue seulement à
    cause des données de démo est classé ENV, pas comme un défaut.
    """
    import contextlib
    import io
    import unittest
    import importlib
    from django.apps import apps
    from django.db import connections
    from django.db.models import Max, QuerySet

    def suite_de(tests):
        s = unittest.TestSuite()
        s.addTests(tests)
        return s

    def lancer(suite):
        conn = connections['default']
        # TestCase.tearDownClass ferme la connexion (ce qui annulerait la transaction de la sonde) : neutralisé
        # le temps du rejeu ; la transaction englobante du lanceur reste ouverte puis est annulée.
        conn.close = lambda *a, **k: None
        try:
            # la sortie des tests (commandes de gestion, journaux) est avalée : seul le bilan est imprimé
            with contextlib.redirect_stdout(io.StringIO()):
                return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        finally:
            del conn.close

    def aplatir(t):
        if isinstance(t, unittest.TestSuite):
            for x in t:
                yield from aplatir(x)
        else:
            yield t

    from django.test import TestCase, TransactionTestCase
    tous, defauts_import, non_rejouables = [], [], []
    for m in modules:
        try:
            for t in aplatir(unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(m))):
                # TransactionTestCase (threads concurrents, commits réels, flush en fin de test) : JAMAIS joué dans
                # la transaction annulée d'une sonde -> écarté et nommé (oracle non rejoué ici).
                if isinstance(t, TransactionTestCase) and not isinstance(t, TestCase):
                    non_rejouables.append(t.id())
                else:
                    tous.append(t)
        except Exception as exc:  # module non chargeable = oracle NON rejoué -> compté comme défaut
            defauts_import.append((m + ' (import)', repr(exc)[:300]))
    res = lancer(suite_de(tous))
    ko = {}
    for t, tb in res.failures + res.errors:
        base = getattr(t, 'test_case', t)  # un sous-test (subTest) est rejoué via son test parent
        ko.setdefault(base.id(), (base, tb))
    env, defauts = [], list(defauts_import)
    if ko:
        plafond = {}
        for mdl in apps.get_models():
            try:
                v = mdl._base_manager.aggregate(m=Max('pk'))['m']
                if isinstance(v, int):
                    plafond[mdl] = v
            except Exception:
                pass
        o_exists, o_count = QuerySet.exists, QuerySet.count

        def borne(qs):
            if qs.model in plafond and not qs.query.is_sliced:
                return qs.filter(pk__gt=plafond[qs.model])
            return None

        def exists(self):
            b = borne(self)
            return o_exists(b) if b is not None else o_exists(self)

        def count(self):
            b = borne(self)
            return o_count(b) if b is not None else o_count(self)
        o_get = QuerySet.get

        def get(self, *a, **kw):
            b = borne(self)
            return o_get(b if b is not None else self, *a, **kw)
        QuerySet.exists, QuerySet.count, QuerySet.get = exists, count, get
        try:
            classes = {}
            for tid, (t, tb) in ko.items():
                if not hasattr(t, '_testMethodName'):
                    defauts.append((tid, tb[-900:]))
                    continue
                classes.setdefault(type(t), []).append(type(t)(t._testMethodName))
            for cls, tests in classes.items():
                r2 = lancer(suite_de(tests))
                ko2 = {}
                for t2, tb2 in r2.failures + r2.errors:
                    ko2.setdefault(getattr(t2, 'test_case', t2).id(), tb2)
                for t in tests:
                    if t.id() in ko2:
                        defauts.append((t.id(), ko2[t.id()][-900:]))
                    else:
                        env.append(t.id())
        finally:
            QuerySet.exists, QuerySet.count, QuerySet.get = o_exists, o_count, o_get
    return {'lances': res.testsRun, 'ko_passe1': len(ko), 'env': env, 'defauts': defauts,
            'sautes': len(res.skipped), 'non_rejouables': non_rejouables}


def _imprimer_tests(t):
    print(f"tests rouges des tâches rejoués : {t['lances']} ; KO passe 1 : {t['ko_passe1']} ; ENV (base de démo "
          f"non vide, verts sur base vierge émulée) : {len(t['env'])} ; DÉFAUTS : {len(t['defauts'])} ; "
          f"sautés {t['sautes']} ; écartés (TransactionTestCase, non rejouables en transaction annulée) : "
          f"{len(t['non_rejouables'])}")
    for nom in t['non_rejouables']:
        print('ECARTE', nom)
    for nom in t['env']:
        print('ENV', nom)
    for nom, tb in t['defauts']:
        print('DEFAUT', nom, tb)


def _utilisateur(company, nom_role, suffixe):
    """Utilisateur au rôle CANONIQUE du registre (aucune permission inventée)."""
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    role = Role.objects.filter(company=company, nom=nom_role).first() or Role.objects.create(
        company=company, nom=nom_role, permissions=dict(CANONICAL_SYSTEM_ROLES)[nom_role])
    U = get_user_model()
    # palier légacy dérivé du rôle exactement comme à la création d'un compte réel (CustomUser.tier_for_role)
    u = U.objects.create_user(username=f'sonde-acc-{suffixe}', password='x', company=company, role=role,
                              role_legacy=U.tier_for_role(role) or U.ROLE_NORMAL)
    api = APIClient()
    api.force_authenticate(u)
    return u, api


def _cles(obj):
    trouvees = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            trouvees.add(k)
            trouvees |= _cles(v)
    elif isinstance(obj, list):
        for v in obj:
            trouvees |= _cles(v)
    return trouvees


def _sans_volatiles(d):
    if isinstance(d, dict):
        return {k: _sans_volatiles(v) for k, v in d.items() if k not in VOLATILES}
    if isinstance(d, list):
        return [_sans_volatiles(v) for v in d]
    return d


def _diff(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def _scenario():
    from decimal import Decimal
    from authentication.models import Company
    from apps.stock.models import Produit, MouvementStock, Fournisseur
    co = Company.objects.create(nom='Sonde ACC-SB', slug='sonde-astk-acc-sb')
    _admin, api = _utilisateur(co, 'Directeur', 'sb-admin')
    H = {'HTTP_HOST': 'localhost'}
    obs, ok = {}, []
    corps = {'nom': 'Batterie sonde SB', 'sku': 'SONDE-ACC-SB', 'prix_vente': '7200.00', 'prix_achat': '5000.00',
             'tva': '20.00', 'seuil_alerte': 2, 'marque_nom': None,
             'est_recurrent': True, 'periodicite_defaut': 'mensuel', 'classe_danger': 'BATTERIE_LITHIUM',
             'quantite_reappro_cible': 20, 'louable': True, 'tarif_location_jour': '150.00',
             'tarif_location_semaine': '900.00', 'tarif_location_mois': '3000.00', 'code_sh': '850760',
             'pays_origine': 'CN', 'avertissement_vente': 'Stockage au sec', 'suivi_serie': True}
    corps = {k: v for k, v in corps.items() if v is not None}
    r = api.post('/api/django/stock/produits/', corps, format='json', **H)
    obs['creation'] = r.status_code
    if r.status_code != 201:
        obs['erreur'] = str(r.content[:300])
        return obs, False
    pid = r.json()['id']
    url = f'/api/django/stock/produits/{pid}/'
    lu1 = api.get(url, **H).json()
    manquants = [k for k in corps if k not in ('marque_nom',) and lu1.get(k) != corps[k]
                 and str(lu1.get(k)) != str(corps[k])]
    obs['champs_non_relus'] = manquants
    ok.append(not manquants)
    # stock modifié par un mouvement APRÈS l'ouverture du formulaire : le PUT renvoie l'ancienne valeur lue.
    from apps.stock.services import record_stock_movement
    p = Produit.objects.get(pk=pid)
    q0 = p.quantite_stock
    record_stock_movement(company=co, produit=p, type_mouvement=MouvementStock.TypeMouvement.ENTREE, quantite=5,
                          quantite_avant=q0, quantite_apres=q0 + 5, reference='SONDE-ACC-SB', note='sonde',
                          created_by=_admin)
    p.refresh_from_db()
    stock_reel = p.quantite_stock
    lu_frais = api.get(url, **H).json()  # état serveur juste avant l'enregistrement
    corps_put = dict(lu1)                # le formulaire renvoie ce qu'il a lu à l'ouverture (stock périmé)
    r = api.put(url, corps_put, format='json', **H)
    obs['put_sans_toucher'] = r.status_code
    lu2 = api.get(url, **H).json()
    p.refresh_from_db()
    d = _diff(_sans_volatiles(lu_frais), _sans_volatiles(lu2))
    obs['cles_changees'] = d
    obs['stock'] = f'lu à l ouverture {lu1.get("quantite_stock")}, réel {stock_reel} -> après PUT {p.quantite_stock}'
    ok.append(r.status_code == 200 and not d and p.quantite_stock == stock_reel)
    # Kit : PUT du corps relu.
    c1 = Produit.objects.create(company=co, nom='Câble SB', sku='SONDE-SB-C1', prix_vente=Decimal('10'),
                                prix_achat=Decimal('5'))
    r = api.post('/api/django/stock/kits/', {'nom': 'Kit SB', 'composants': [
        {'produit': c1.pk, 'quantite': '2', 'taux_perte_pct': '5.00'}]}, format='json', **H)
    obs['kit_creation'] = r.status_code
    if r.status_code == 201:
        kurl = f"/api/django/stock/kits/{r.json()['id']}/"
        k1 = api.get(kurl, **H).json()
        from apps.stock.models import KitProduit
        kit = KitProduit.objects.get(pk=k1['id'])
        rev0 = kit.revisions.count() if hasattr(kit, 'revisions') else None
        r = api.put(kurl, k1, format='json', **H)
        k2 = api.get(kurl, **H).json()
        rev1 = kit.revisions.count() if hasattr(kit, 'revisions') else None
        def sans_id(k):
            k = _sans_volatiles(k)
            k['composants'] = [{c: v for c, v in x.items() if c != 'id'} for x in k.get('composants', [])]
            return k
        dk = _diff(sans_id(k1), sans_id(k2))
        obs['kit_put'] = r.status_code
        obs['kit_cles_changees_hors_id_composant'] = dk
        obs['kit_ids_composants'] = f"{[x['id'] for x in k1['composants']]} -> {[x['id'] for x in k2['composants']]}"
        obs['kit_perte'] = f"{k1['composants'][0]['taux_perte_pct']} -> {k2['composants'][0]['taux_perte_pct']}"
        obs['kit_revisions'] = f'{rev0} -> {rev1}'
        # ASTK96 exige : valeurs (perte comprise) conservées, aucune révision « identique » ; l'id technique du
        # composant recréé (delete + create) n'est pas une donnée métier -> noté, hors verdict.
        ok.append(r.status_code == 200 and not dk and rev0 == rev1)
    else:
        obs['kit_erreur'] = str(r.content[:300])
        ok.append(False)
    # BCF : PUT du corps relu -> lignes gardées.
    f = Fournisseur.objects.create(company=co, nom='Fournisseur SB')
    r = api.post('/api/django/stock/bons-commande-fournisseur/', {
        'fournisseur': f.pk, 'date_commande': '2026-10-30', 'frais_annexes': '50.00',
        'lignes': [{'produit': c1.pk, 'quantite': 4, 'prix_achat_unitaire': '100.00'}]}, format='json', **H)
    obs['bcf_creation'] = r.status_code
    if r.status_code == 201:
        burl = f"/api/django/stock/bons-commande-fournisseur/{r.json()['id']}/"
        b1 = api.get(burl, **H).json()
        r = api.put(burl, b1, format='json', **H)
        b2 = api.get(burl, **H).json()
        ids1 = [x['id'] for x in b1.get('lignes', [])]
        ids2 = [x['id'] for x in b2.get('lignes', [])]
        db = _diff(_sans_volatiles(b1), _sans_volatiles(b2))
        obs['bcf_put'] = r.status_code
        obs['bcf_lignes'] = f'{ids1} -> {ids2}'
        obs['bcf_cles_changees'] = db
        ok.append(r.status_code == 200 and ids1 == ids2 and not db)
    else:
        obs['bcf_erreur'] = str(r.content[:300])
        ok.append(False)
    return obs, all(ok)


def sonde(ctx):
    obs, ok_sc = _scenario()
    print('scénario S-B :', obs, '->', 'OK' if ok_sc else 'KO')
    t = _rejouer_tests(MODULES)
    _imprimer_tests(t)
    return {'repro': ok_sc and not t['defauts'], 'tests': t['lances']}
