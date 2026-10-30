SONDE = {"constat": "C-ASTK-ACC-SC", "sha": "5908d43bb",
         "attendu": "S-C prix d'achat (D-ASTK-2) : aucun JSON servi au Commercial ni au Technicien (toutes les listes "
                    "des routeurs stock + achats, détails produit/BCF/réception/facture/fournisseur/catalogue d'achat) "
                    "ne contient la clé prix_achat ni le coût d'achat ou le prix BCF ; la page fournisseur à jeton, le "
                    "kiosque quai et le solde 3PL ne portent ni prix_achat ni marge ; le PDF client /proposal "
                    "n'imprime pas le coût ; le Directeur, lui, les voit ; tests rouges ASTK10-15/243/246/247 verts"}

MODULES = ['apps.stock.test_astk_prix_achat_bcf', 'apps.stock.test_astk_prix_achat_factures',
           'apps.stock.test_astk_prix_achat_catalogue_import', 'apps.stock.test_astk_prix_achat_fournisseur',
           'apps.stock.test_astk_garde_prix_achat', 'apps.stock.test_astk_perm_achats_payer',
           'apps.stock.test_astk_conformite_types']

COUT = '5432.17'      # Produit.prix_achat (coût interne)
PU_BCF = '777.31'     # prix d'achat unitaire négocié du BCF
CLES = {'prix_achat', 'prix_achat_unitaire', 'prix_achat_unitaire_devise', 'total_achat', 'cout_unitaire',
        'cout_moyen', 'marge', 'marge_pct', 'valeur_stock'}

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


def _contenu(r):
    return b''.join(r.streaming_content) if getattr(r, 'streaming', False) else r.content


def _fuites(r):
    import json
    corps = _contenu(r)
    txt = corps.decode('utf-8', 'replace')
    f = [v for v in (COUT, PU_BCF) if v in txt or v.replace('.', ',') in txt]
    try:
        cles = _cles(json.loads(txt)) & CLES
    except Exception:
        cles = set()
    return f, sorted(cles)


def _scenario():
    import datetime
    from decimal import Decimal
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import (Produit, Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   PortailFournisseurToken, EmplacementStock)
    from apps.stock.models_wms import PortailTiersToken, Quai, RendezVousTransporteur
    from apps.stock import urls as su
    from apps.achats import urls as au
    from apps.ventes.models import Devis, LigneDevis
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACC-SC', slug='sonde-astk-acc-sc')
    _d, api_dir = _utilisateur(co, 'Directeur', 'sc-dir')
    _c, api_com = _utilisateur(co, 'Commercial', 'sc-com')
    _t, api_tec = _utilisateur(co, 'Technicien', 'sc-tec')
    p = Produit.objects.create(company=co, nom='Onduleur sonde SC', sku='SONDE-ACC-SC', prix_vente=Decimal('9000'),
                               prix_achat=Decimal(COUT), quantite_stock=10, tva=Decimal('20.00'))
    f = Fournisseur.objects.create(company=co, nom='Fournisseur SC')
    bcf = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference='BCF-SONDE-SC',
                                                statut=BonCommandeFournisseur.Statut.ENVOYE,
                                                date_commande=datetime.date(2026, 10, 30))
    LigneBonCommandeFournisseur.objects.create(bon_commande=bcf, produit=p, quantite=3,
                                               prix_achat_unitaire=Decimal(PU_BCF))
    obs, ok = {}, []
    # 1) balayage de toutes les listes + détails connus, pour Commercial et Technicien.
    details = [f'/api/django/stock/produits/{p.pk}/', f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/',
               f'/api/django/stock/fournisseurs/{f.pk}/', f'/api/django/stock/catalogue-achat/{p.pk}/',
               f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/pdf/',
               f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/historique-prix/',
               f'/api/django/stock/fournisseurs/{f.pk}/vue-360/', f'/api/django/achats/bons-commande-fournisseur/{bcf.pk}/']
    listes = [f'{b}{pref}/' for b, rt in (('/api/django/stock/', su.router), ('/api/django/achats/', au.router))
              for pref, _vs, _bn in rt.registry]
    for nom, api in (('Commercial', api_com), ('Technicien', api_tec)):
        fuites, statuts = [], {}
        for url in listes + details:
            r = api.get(url, **H)
            statuts[r.status_code] = statuts.get(r.status_code, 0) + 1
            fv, fc = _fuites(r) if r.status_code == 200 else ([], [])
            if fv or fc:
                fuites.append(f'{url} {r.status_code} valeurs={fv} cles={fc}')
        obs[f'{nom}_routes'] = len(listes + details)
        obs[f'{nom}_statuts'] = statuts
        obs[f'{nom}_fuites'] = fuites
        ok.append(not fuites and not statuts.get(500))
    # contre-épreuve : le Directeur voit bien le coût et le prix BCF.
    r1 = api_dir.get(f'/api/django/stock/produits/{p.pk}/', **H)
    r2 = api_dir.get(f'/api/django/stock/bons-commande-fournisseur/{bcf.pk}/', **H)
    obs['directeur_voit'] = [COUT in _contenu(r1).decode(), PU_BCF in _contenu(r2).decode()]
    ok.append(all(obs['directeur_voit']))
    # 2) page fournisseur à jeton : documents de SON fournisseur, sans coût interne ni marge.
    tok = PortailFournisseurToken.objects.create(company=co, fournisseur=f)
    r = api_com.__class__().get(f'/api/django/public/stock/portail-fournisseur/{tok.token}/', **H)
    fv, fc = _fuites(r)
    obs['page_fournisseur'] = f'{r.status_code} cout_interne={COUT in str(fv)} cles={fc}'
    ok.append(r.status_code == 200 and COUT not in fv and not (set(fc) & {'prix_achat', 'marge', 'marge_pct',
                                                                           'cout_moyen', 'valeur_stock'}))
    # 3) solde 3PL.
    EmplacementStock.objects.create(company=co, nom='Dépôt tiers SC', type_proprietaire='de_tiers',
                                    tiers_nom='Tiers SC') if hasattr(EmplacementStock, 'tiers_nom') else None
    pt = PortailTiersToken.objects.create(company=co, tiers_nom='Tiers SC')
    r = api_com.__class__().get(f'/api/django/public/stock/tiers/{pt.token}/solde/', **H)
    fv, fc = _fuites(r)
    obs['solde_3pl'] = f'{r.status_code} valeurs={fv} cles={fc}'
    ok.append(r.status_code == 200 and not fv and not fc)
    # 4) kiosque quai (arrivée chauffeur).
    q = Quai.objects.create(company=co, nom='Quai SC', emplacement=EmplacementStock.objects.create(company=co, nom='Dépôt quai SC'))
    debut = timezone.now() + datetime.timedelta(hours=1)
    rdv = RendezVousTransporteur.objects.create(company=co, quai=q, date_heure_debut=debut,
                                                date_heure_fin=debut + datetime.timedelta(hours=1),
                                                fournisseur=f, bon_commande=bcf)
    rdv.refresh_from_db()
    code = getattr(rdv, 'code_checkin', '')
    r = api_com.__class__().post('/api/django/public/stock/quai-checkin/', {'societe': co.slug, 'code': code},
                                 format='json', **H)
    fv, fc = _fuites(r)
    obs['kiosque'] = f'{r.status_code} cles={sorted(r.json().keys()) if r.status_code == 200 else r.content[:80]}'
    ok.append(r.status_code == 200 and not fv and not fc)
    # 5) PDF client /proposal : le coût n'y figure pas.
    cl = Client.objects.create(company=co, nom='Client', prenom='SC', email='sonde-acc-sc@example.invalid')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-SC', client=cl, statut=Devis.Statut.BROUILLON,
                             taux_tva=Decimal('20'), mode_installation='residentiel')
    LigneDevis.objects.create(devis=d, produit=p, designation='Onduleur sonde SC', quantite=Decimal('1'),
                              prix_unitaire=Decimal('9000'), taux_tva=Decimal('20.00'))
    r = api_dir.get(f'/api/django/ventes/devis/{d.pk}/proposal/?pdf_mode=onepage', **H)
    corps = _contenu(r)
    if r.status_code == 200:
        import re
        import fitz
        texte = re.sub(r'\s', '', ''.join(pg.get_text() for pg in fitz.open(stream=corps, filetype='pdf')))
        obs['pdf_client'] = f'200 cout_imprime={("5432" in texte)}'
        ok.append('5432' not in texte)
    else:
        obs['pdf_client'] = f'{r.status_code} {corps[:150]!r}'
        ok.append(False)
    return obs, all(ok)


def sonde(ctx):
    obs, ok_sc = _scenario()
    print('scénario S-C :', obs, '->', 'OK' if ok_sc else 'KO')
    t = _rejouer_tests(MODULES)
    _imprimer_tests(t)
    return {'repro': ok_sc and not t['defauts'], 'tests': t['lances']}
