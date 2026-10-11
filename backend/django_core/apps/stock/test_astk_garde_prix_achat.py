"""ASTK14 (C-ASTK-002, S2) — garde de CLASSE « prix d'achat servi sans gate ».

Un test balaie, par INTROSPECTION des routeurs ``apps/stock/urls.py`` et
``apps/achats/urls.py`` (aucune liste manuelle de routes), toutes les routes GET
(list, retrieve et actions ``@action`` en lecture) avec un compte Commercial et
un compte Viewer (sans ``prix_achat_voir``) sur une société seedée, et échoue si
un JSON de réponse 200 contient une clé de prix ou de montant d'achat.

Routes exemptées par une règle NOMMÉE (réponse non JSON : PDF/XLSX/HTML), jamais
par numéro de ligne. ASTK243 : chaque route est appelée avec des paramètres
VALIDES (``PARAMETRES_PAR_ROUTE``) et toute réponse non-200 est une ERREUR
nommée, sauf le 403 d'une permission DÉCLARÉE (``get_permissions``, lue par
introspection) qui refuse ce rôle — un 400 ne cache plus jamais un corps.

Contrôle positif : l'Administrateur voit au moins une de ces clés sur les mêmes
données (sinon la garde balaierait un jeu de données vide).

Run :
    python manage.py test apps.stock.test_astk_garde_prix_achat -v 2
"""
import datetime
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import (
    AcompteFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    FactureFournisseur, Fournisseur, LigneBonCommandeFournisseur, LigneFactureFournisseur, LotEntrepot,
    PaiementFournisseur, PalierPrixFournisseur, PrixFournisseur, Produit,
)
from apps.stock.models import BudgetDepartement, EngagementBudget
from apps.stock.models_incident_fournisseur import IncidentQualiteFournisseur
from apps.stock.models_rfa import AccordRFAFournisseur
from apps.stock.models_wms import UniteLogistique
from authentication.models import Company

User = get_user_model()

RACINES = {
    'apps.stock.urls': '/api/django/stock/',
    'apps.achats.urls': '/api/django/achats/',
}
CLES_EXACTES = {
    'prix_achat', 'prix_unitaire_ht', 'prix_convenu', 'montant_achete',
    'frais_annexes', 'paiements', 'montant',
    # ERR-STK-PRIX-ACHAT-SUITE — valeurs de stock/pertes au coût d'achat.
    'total_valeur', 'valeur',
}
PREFIXES_CLES = ('prix_achat_', 'total_achat', 'montant_', 'cout_')
RE_PK = re.compile(r'\(\?P<pk>[^)]*\)')
#: ERR-STK-PRIX-ACHAT-SUITE — chemins SIMPLES (hors routeur) balayés aussi.
CHEMINS_SIMPLES = ('/api/django/stock/tableau-bord-achats/',
                   '/api/django/stock/entrepot/pertes/')
#: ASTK243 — paramètres VALIDES (objets de démo du ``setUp``) des routes qui
#: répondent 400 sans eux : suffixe de gabarit → fabrique(test).
PARAMETRES_PAR_ROUTE = {
    'factures-fournisseur/suggestions-bcf/': lambda t: {'fournisseur': t.fournisseur.id},
    'bons-commande-fournisseur/bcf-similaires/': lambda t: {'fournisseur': t.fournisseur.id},
    'lots-entrepot/fefo/': lambda t: {'produit': t.produit.id},
    'produits/etiquettes-prix/': lambda t: {'ids': t.produit.id, 'sortie': 'html'},
    'produits/resolve/': lambda t: {'code': t.produit.code_barres},
    'receptions-fournisseur/scan-gs1/': lambda t: {'code': '01' + t.produit.code_barres},
    'produits/tracer/': lambda t: {'lot': t.lot.numero_lot},
    'produits/tracabilite/': lambda t: {'lot': t.lot.numero_lot},
    'quais/planning/': lambda t: {'date': '2026-09-01'},
    'expeditions/tarifs/': lambda t: {'unite_logistique': t.unite.id},
    # GET emplacements/ CRÉE « Dépôt principal » + « Camionnette »
    # (ensure_emplacements) : leurs cartes kanban exigent `ids`.
    'etiquettes-kanban/': lambda t: {'ids': t.produit.id, 'sortie': 'html'},
    'unites-logistiques/{pk}/etiquette-pdf/': lambda t: {'sortie': 'html'},
}


def cles_interdites(payload):
    """Ensemble des clés d'achat présentes (récursif)."""
    trouvees = set()
    if isinstance(payload, dict):
        for cle, valeur in payload.items():
            if cle in CLES_EXACTES or cle.startswith(PREFIXES_CLES):
                trouvees.add(cle)
            trouvees |= cles_interdites(valeur)
    elif isinstance(payload, list):
        for valeur in payload:
            trouvees |= cles_interdites(valeur)
    return trouvees


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def routes_get():
    """[(url_relative_gabarit, kind)] lues sur les routeurs (introspection).

    ``kind`` ∈ {'list', 'detail', 'detail_action', 'liste_action'} ; le gabarit
    contient ``{pk}`` pour les routes de détail. Les routes à suffixe de format
    ou à paramètre d'URL autre que ``pk`` sont ignorées (non balayables).
    """
    import importlib
    trouvees = []
    for module_nom, base in RACINES.items():
        module = importlib.import_module(module_nom)
        for motif in module.router.get_urls():
            regex = motif.pattern.regex.pattern
            actions = getattr(motif.callback, 'actions', None) or {}
            if 'get' not in actions or 'format' in regex:
                continue
            gabarit = RE_PK.sub('{pk}', regex).lstrip('^').rstrip('$')
            if '(?P<' in gabarit or '\\' in gabarit:
                continue
            detail = '{pk}' in gabarit
            nom_action = actions['get']
            if nom_action == 'list':
                kind = 'list'
            elif nom_action == 'retrieve':
                kind = 'detail'
            else:
                kind = 'detail_action' if detail else 'liste_action'
            trouvees.append((base + gabarit, kind))
    trouvees += [(chemin, 'liste_action') for chemin in CHEMINS_SIMPLES]
    return sorted(set(trouvees))


def refus_declare(cible, utilisateur):
    """ASTK243 — vrai si une permission DÉCLARÉE de la route
    (``get_permissions``, lue par introspection) refuse ce rôle."""
    from django.urls import resolve
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory
    route = resolve(cible)
    vue = route.func.cls(**(getattr(route.func, 'initkwargs', None) or {}))
    if getattr(route.func, 'actions', None):  # viewset ; sinon @api_view
        vue.action_map, vue.action = route.func.actions, route.func.actions['get']
    vue.args, vue.kwargs, vue.format_kwarg = (), route.kwargs, None
    vue.request = Request(APIRequestFactory().get(cible))
    vue.request.user = utilisateur
    return any(not p.has_permission(vue.request, vue)
               for p in vue.get_permissions())


def balayer(api, routes, utilisateur, fixtures=None):
    """GET de chaque route avec ses paramètres VALIDES (``fixtures`` = le test,
    lu par ``PARAMETRES_PAR_ROUTE``) ; renvoie (violations, nb_json_200,
    erreurs) — ``erreurs`` nomme chaque non-200 qui n'est pas un refus
    déclaré (ASTK243 : jamais sauté en silence)."""
    ids, violations, erreurs, nb_json = {}, [], [], 0

    def _get(gabarit, cible):
        nonlocal nb_json
        params = next((f(fixtures) for s, f in PARAMETRES_PAR_ROUTE.items()
                       if fixtures is not None and gabarit.endswith(s)), {})
        reponse = api.get(cible, params)
        if reponse.status_code != 200:
            if reponse.status_code != 403 or not refus_declare(cible, utilisateur):
                erreurs.append(f'GET {cible} -> HTTP {reponse.status_code} {getattr(reponse, "data", "")}')
            return None
        # Règle d'exemption nommée : réponse non JSON (PDF, XLSX, HTML).
        if 'json' not in (reponse.get('Content-Type') or ''):
            return None
        nb_json += 1
        donnees = reponse.json()
        trouvees = cles_interdites(donnees)
        if trouvees:
            violations.append(f'GET {cible} -> {sorted(trouvees)}')
        return donnees

    # 1) listes d'abord : elles fournissent un pk réel par ressource.
    for url, kind in routes:
        if kind != 'list':
            continue
        donnees = _get(url, url)
        lignes = donnees.get('results') if isinstance(donnees, dict) \
            else donnees
        if isinstance(lignes, list) and lignes \
                and isinstance(lignes[0], dict) and 'id' in lignes[0]:
            ids[url] = lignes[0]['id']
    # 2) le reste.
    for url, kind in routes:
        if kind == 'list':
            continue
        pk = ids.get(url.split('{pk}')[0]) if '{pk}' in url else ''
        if pk is None:
            continue
        _get(url, url.replace('{pk}', str(pk)))
    return violations, nb_json, erreurs


class GardePrixAchat(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK14', slug='astk14-co')
        perms = dict(CANONICAL_SYSTEM_ROLES)

        def _role_user(nom):
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=perms[nom])
            return User.objects.create_user(
                username=f'astk14-{nom.lower()}', password='x',
                company=self.company, role=role)

        self.commercial = _role_user('Commercial')
        self.viewer = _role_user('Viewer')
        self.admin = _role_user('Administrateur')
        self.assertFalse(self.commercial.can_view_buy_prices)
        self.assertFalse(self.viewer.can_view_buy_prices)
        self.assertTrue(self.admin.can_view_buy_prices)

        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK14')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK14', sku='ASTK14-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('900'),
            fournisseur=self.fournisseur, code_barres='03760000000019')
        # ASTK243 — objets que les fabriques de paramètres désignent.
        self.lot = LotEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_lot='LOT-ASTK14')
        self.unite = UniteLogistique.objects.create(
            company=self.company, sscc='037600000000000017',
            statut=UniteLogistique.Statut.SCELLE)
        prix = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('820.00'))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=prix, qte_min=10, prix=Decimal('780.00'))
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK14-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_commande=datetime.date.today())
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK14-1',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('833.33'), montant_tva=Decimal('166.67'),
            montant_ttc=Decimal('1000'))
        LigneFactureFournisseur.objects.create(
            facture=facture, designation='Prestation', quantite=1,
            prix_unitaire_ht=Decimal('833.33'))
        PaiementFournisseur.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('400'), date_paiement=datetime.date(2026, 9, 10))
        # ASTK247 — un acompte et un avoir VALIDÉ de démo (montants réglés).
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('820'))
        AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-ASTK14-1',
            fournisseur=self.fournisseur, montant_ht=Decimal('100'),
            montant_tva=Decimal('20'), montant_ttc=Decimal('120'),
            statut=AvoirFournisseur.Statut.VALIDE)
        # ERR-STK-PRIX-ACHAT-SUITE — un objet de chaque type à montant d'achat.
        from apps.stock.services import creer_expedition_transporteur
        budget = BudgetDepartement.objects.create(
            company=self.company, annee=2026, montant_alloue=Decimal('50000'))
        EngagementBudget.objects.create(
            company=self.company, budget=budget, montant=Decimal('820'))
        creer_expedition_transporteur(
            company=self.company, unite=self.unite, cout_reel=Decimal('180'))
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=datetime.date(2026, 9, 2), cout_impact_mad=Decimal('300'))
        AccordRFAFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            periode_debut=datetime.date(2026, 1, 1),
            periode_fin=datetime.date(2026, 12, 31),
            seuil_ca_achat=Decimal('5000'), montant_fixe=Decimal('400'))

    def test_introspection_non_vide(self):
        """Le balayage découvre bien les routes (garde contre une
        introspection silencieusement vide)."""
        routes = routes_get()
        self.assertGreater(len(routes), 40, routes)
        urls = {u for u, _ in routes}
        self.assertTrue(any('bons-commande-fournisseur' in u for u in urls))
        self.assertTrue(any('factures-fournisseur' in u for u in urls))

    def test_aucune_route_ne_sert_de_prix(self):
        routes = routes_get()
        for utilisateur in (self.commercial, self.viewer):
            violations, nb_json, erreurs = balayer(
                _api(utilisateur), routes, utilisateur, self)
            self.assertGreater(nb_json, 5, utilisateur.username)
            self.assertEqual(
                violations, [],
                f'{utilisateur.username} reçoit des clés de prix/montant '
                "d'achat :\n" + '\n'.join(violations))
            self.assertEqual(erreurs, [], f'{utilisateur.username} : réponses '
                             'non-200 du balayage :\n' + '\n'.join(erreurs))

    def test_suggestions_bcf_sans_montant_et_balayage_sans_non_200(self):
        """ASTK243 — `suggestions-bcf` balayée AVEC un fournisseur valide :
        200, le BCF de démo proposé, aucune clé `montant_*` ; sans paramètre,
        son 400 est une erreur NOMMÉE du balayage, plus jamais sautée."""
        url = '/api/django/stock/factures-fournisseur/suggestions-bcf/'
        api, routes = _api(self.commercial), [(url, 'liste_action')]
        self.assertEqual(
            [r['reference'] for r in api.get(
                url, {'fournisseur': self.fournisseur.id}).json()],
            ['BCF-ASTK14-1'])
        self.assertEqual(balayer(api, routes, self.commercial, self),
                         ([], 1, []))
        _, _, erreurs = balayer(api, routes, self.commercial)
        self.assertEqual(len(erreurs), 1, erreurs)
        self.assertIn(f'GET {url} -> HTTP 400', erreurs[0])

    def test_trois_routes_prix_achat_err_stk(self):
        """ERR-STK-PRIX-ACHAT-3-ROUTES — comparer-tco (`prix_nu` = prix
        d'achat) et analyse-achats : 403 DÉCLARÉ (PeutVoirPrixAchat) pour
        Commercial ; budgets-departement/disponible : le verdict sans aucun
        montant. L'Administrateur reçoit les montants sur les trois."""
        tco = f'/api/django/stock/produits/{self.produit.id}/comparer-tco/'
        analyse = '/api/django/stock/produits/analyse-achats/'
        budget = '/api/django/stock/budgets-departement/disponible/'
        commercial, admin = _api(self.commercial), _api(self.admin)
        for url in (tco, analyse):
            self.assertEqual(commercial.get(url).status_code, 403, url)
            self.assertTrue(refus_declare(url, self.commercial), url)
        self.assertIn('prix_nu', admin.get(tco).json()['fournisseurs'][0])
        self.assertTrue(cles_interdites(admin.get(analyse).json()))
        rep = commercial.get(budget, {'montant': '100'})
        self.assertEqual((rep.status_code, set(rep.json())),
                         (200, {'controle_actif', 'suffisant', 'budget_id'}))
        self.assertIn('montant_alloue', admin.get(budget).json())

    def test_suite_routes_masquees_mais_administrateur_servi(self):
        """ERR-STK-PRIX-ACHAT-SUITE — l'Administrateur (prix_achat_voir) garde
        les montants des cinq ressources et des deux chemins simples ; le
        Commercial reçoit les mêmes lignes SANS ces clés (ou un 403 déclaré)."""
        def lignes(donnees):
            return donnees['results'] if isinstance(donnees, dict) else donnees
        admin, commercial = _api(self.admin), _api(self.commercial)
        for suffixe, cle in (('budgets-departement/', 'montant_alloue'),
                             ('engagements-budget/', 'montant'),
                             ('expeditions/', 'cout_reel'),
                             ('incidents-qualite-fournisseur/', 'cout_impact_mad'),
                             ('accords-rfa-fournisseur/', 'montant_fixe')):
            url = f'/api/django/stock/{suffixe}'
            self.assertIn(cle, lignes(admin.get(url).json())[0], url)
            rep = commercial.get(url)
            self.assertEqual(rep.status_code, 200, url)
            self.assertNotIn(cle, lignes(rep.json())[0], url)
        pertes = '/api/django/stock/entrepot/pertes/'
        self.assertIn('total_valeur', admin.get(pertes).json())
        self.assertNotIn('total_valeur', commercial.get(pertes).json())
        tableau = '/api/django/stock/tableau-bord-achats/'
        self.assertEqual(admin.get(tableau).status_code, 200)
        self.assertEqual(commercial.get(tableau).status_code, 403)
        self.assertTrue(refus_declare(tableau, self.commercial))

    def test_controle_positif_administrateur(self):
        """L'Administrateur voit ces clés sur les mêmes données : la garde
        scanne donc un jeu de données qui en contient réellement."""
        violations, _, _ = balayer(
            _api(self.admin), routes_get(), self.admin, self)
        self.assertTrue(violations, "l'admin ne voit aucune clé d'achat : jeu "
                                    'de données vide ou garde aveugle')

    def test_le_detecteur_nomme_les_cles(self):
        """Test-du-test : le détecteur de clés repère chaque famille."""
        plante = {'results': [{'prix_achat': 1, 'x': {'prix_achat_devise': 2}},
                              {'total_achats_ht': 3, 'prix_convenu': 4,
                               'lignes': [{'frais_annexes': 5,
                                           'prix_unitaire_ht': 6}],
                               'paiements': [], 'montant_achete': 7,
                               'montant_total': 8, 'cout_retard': 9,
                               'montant': 10}]}
        self.assertEqual(cles_interdites(plante), {
            'prix_achat', 'prix_achat_devise', 'total_achats_ht',
            'prix_convenu', 'frais_annexes', 'prix_unitaire_ht', 'paiements',
            'montant_achete', 'montant_total', 'cout_retard', 'montant'})
        self.assertEqual(cles_interdites({'quantite': 1, 'prix_vente': 2}),
                         set())
