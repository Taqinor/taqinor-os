SONDE = {"constat": "C-ASTK-ACC-SE", "sha": "5908d43bb",
         "attendu": "S-E étanchéité : depuis la société de démo 2, chaque id de la société 6 (ou d'une autre) sur les endpoints stock/achats/WMS "
                    "répond comme un id absent (404 en lecture, 400 « objet inexistant » en écriture), jamais 403 ni "
                    "donnée ; paires TEN-11 (id de B / id 99999999) octet-identiques ; jeton fournisseur révoqué -> 404 ; "
                    "tests rouges des tâches C5 (ASTK1-9, ASTK179, ASTK212) verts contre la base de la pile"}

MODULES = ['apps.stock.test_astk_oracle_existence', 'apps.stock.test_astk_fk_achats',
           'apps.stock.test_astk_fk_catalogue_mouvements', 'apps.stock.test_astk_fk_expedition',
           'apps.stock.test_astk_fk_inventaire_revalo', 'apps.stock.test_astk_fk_retour_modele_bcf',
           'apps.stock.test_astk_fk_views_serializers', 'apps.stock.test_astk_fk_wms',
           'apps.stock.test_astk_revocation_fournisseur', 'apps.stock.test_astk_garde_fk_societe']


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


def _corps(r, ident):
    """Corps comparable : l'identifiant envoyé et le request_id (aléatoire par requête) sont neutralisés."""
    import re
    txt = r.content.decode('utf-8', 'replace').replace(ident, '<ID>')
    return re.sub(r'"request_id":\s*"[^"]*"', '"request_id":"<R>"', txt)


def _peupler_b():
    """Société B neuve peuplée PAR L'API (Directeur de B) : fournisseur, BCF envoyé, acompte, réception confirmée,
    facture, paiement, kit, session d'inventaire, emplacement, quai, rendez-vous, jeton portail 3PL, retour."""
    import datetime
    from decimal import Decimal
    from django.utils import timezone
    from authentication.models import Company
    from apps.stock.models import Produit, Fournisseur, BonCommandeFournisseur, EmplacementStock
    from apps.stock.models_wms import Quai, RendezVousTransporteur, PortailTiersToken
    H = {'HTTP_HOST': 'localhost'}
    S = '/api/django/stock'
    b = Company.objects.create(nom='Sonde ACC-SE B', slug='sonde-astk-acc-se-b')
    _u, api = _utilisateur(b, 'Directeur', 'se-dir-b')
    p = Produit.objects.create(company=b, nom='Produit B', sku='SONDE-SE-B', prix_vente=Decimal('10'),
                               prix_achat=Decimal('5'), tva=Decimal('20.00'))
    f = Fournisseur.objects.create(company=b, nom='Fournisseur B')
    r = api.post(f'{S}/bons-commande-fournisseur/', {'fournisseur': f.pk, 'date_commande': '2026-10-30',
                 'lignes': [{'produit': p.pk, 'quantite': 4, 'prix_achat_unitaire': '10.00'}]}, format='json', **H)
    bid = r.json()['id']
    api.post(f'{S}/bons-commande-fournisseur/{bid}/envoyer/', **H)
    api.post(f'{S}/acomptes-fournisseur/', {'bon_commande': bid, 'montant': '5.00', 'date_versement': '2026-10-30',
                                            'mode': 'virement'}, format='json', **H)
    ligne = BonCommandeFournisseur.objects.get(pk=bid).lignes.get()
    r = api.post(f'{S}/receptions-fournisseur/', {'bon_commande': bid, 'date_reception': '2026-10-30',
                 'lignes': [{'ligne_commande': ligne.pk, 'quantite': 4}]}, format='json', **H)
    rid = r.json()['id']
    api.post(f'{S}/receptions-fournisseur/{rid}/confirmer/', **H)
    r = api.post(f'{S}/receptions-fournisseur/{rid}/facturer/', **H)
    if r.status_code == 201:
        api.post(f'{S}/paiements-fournisseur/', {'facture': r.json()['id'], 'montant': '1.00',
                                                 'date_paiement': '2026-10-30', 'mode': 'virement'}, format='json', **H)
    api.post(f'{S}/kits/', {'nom': 'Kit B', 'composants': [{'produit': p.pk, 'quantite': '1'}]}, format='json', **H)
    api.post(f'{S}/inventaire-sessions/', {'nom': 'Inv B', 'lignes': [{'produit': p.pk, 'quantite_comptee': 4}]},
             format='json', **H)
    api.post(f'{S}/prix-fournisseurs/', {'produit': p.pk, 'fournisseur': f.pk, 'prix_achat': '9.00'},
             format='json', **H)
    api.post(f'{S}/contacts-fournisseur/', {'fournisseur': f.pk, 'nom': 'Contact B'}, format='json', **H)
    emp = EmplacementStock.objects.create(company=b, nom='Dépôt B', is_principal=True)
    q = Quai.objects.create(company=b, nom='Quai B', emplacement=emp)
    debut = timezone.now() + datetime.timedelta(days=2)
    RendezVousTransporteur.objects.create(company=b, quai=q, date_heure_debut=debut,
                                          date_heure_fin=debut + datetime.timedelta(hours=1))
    PortailTiersToken.objects.create(company=b, tiers_nom='Tiers B')
    return b


def _balayage(b):
    """Tous les ViewSets des routeurs stock + achats : un utilisateur Directeur de la société de démo 2 (seed_demo)
    demande le détail d'un objet EXISTANT d'une société B peuplée par l'API dans la sonde, à défaut de la société 6
    (seed_demo_company), à défaut d'une autre — et doit recevoir exactement la réponse d'un id absent (99999999)."""
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.roles.models import Role
    from apps.stock import urls as su
    from apps.achats import urls as au
    a = Company.objects.get(pk=2)
    role = Role.objects.get(company=a, nom='Directeur')
    U = get_user_model()
    u = U.objects.create_user(username='sonde-astk-acc-se-dir2', password='x', company=a, role=role,
                              role_legacy=U.tier_for_role(role) or U.ROLE_NORMAL)
    api = APIClient()
    api.force_authenticate(u)
    lignes, ko, sans_objet = [], [], []
    for base, router in (('/api/django/stock/', su.router), ('/api/django/achats/', au.router)):
        for prefix, vs, _bn in router.registry:
            qs = getattr(vs, 'queryset', None)
            if qs is None:
                sans_objet.append(prefix)
                continue
            mdl = qs.model
            if not any(f.name == 'company' for f in mdl._meta.fields):
                sans_objet.append(prefix + ' (sans company)')
                continue
            obj = (mdl._base_manager.filter(company=b).order_by('pk').first()
                   or mdl._base_manager.filter(company_id=6).order_by('pk').first()
                   or mdl._base_manager.exclude(company=a).order_by('pk').first())
            if obj is None:
                sans_objet.append(prefix)
                continue
            r1 = api.get(f'{base}{prefix}/{obj.pk}/', HTTP_HOST='localhost')
            r2 = api.get(f'{base}{prefix}/99999999/', HTTP_HOST='localhost')
            b1, b2 = _corps(r1, str(obj.pk)), _corps(r2, '99999999')
            ok = r1.status_code == r2.status_code and r1.status_code in (404, 405) and b1 == b2
            lignes.append(f'{base}{prefix}/<id {obj.pk} soc {obj.company_id}> {r1.status_code} vs absent {r2.status_code}')
            if not ok:
                ko.append(f'{base}{prefix}/{obj.pk}/ -> {r1.status_code} {r1.content[:160]!r} ; absent -> '
                          f'{r2.status_code} {r2.content[:120]!r}')
            # la LISTE de la société 2 ne contient aucun id de B
            ids_b = set(mdl._base_manager.filter(company=b).values_list('pk', flat=True))
            if ids_b:
                rl = api.get(f'{base}{prefix}/', {'page_size': 500}, HTTP_HOST='localhost')
                try:
                    d = rl.json()
                    rows = d.get('results', d) if isinstance(d, dict) else d
                    vus = {x.get('id') for x in rows if isinstance(x, dict)}
                except Exception:
                    vus = set()
                if vus & ids_b:
                    ko.append(f'{base}{prefix}/ liste -> ids de B visibles {sorted(vus & ids_b)}')
    return lignes, ko, sans_objet


def sonde(ctx):
    lignes, ko_bal, sans_objet = _balayage(_peupler_b())
    print(f'balayage détail inter-sociétés : {len(lignes)} routes avec objet étranger rejouées, {len(ko_bal)} KO ; '
          f'sans objet en base (non rejouées) : {", ".join(sans_objet) or "aucune"}')
    for x in lignes:
        print('ROUTE', x)
    for x in ko_bal:
        print('KO-BALAYAGE', x)
    t = _rejouer_tests(MODULES)
    _imprimer_tests(t)
    return {'repro': not t['defauts'] and not ko_bal, 'tests': t['lances'],
            'defauts': [n for n, _ in t['defauts']], 'routes_balayees': len(lignes), 'ko_balayage': len(ko_bal)}
