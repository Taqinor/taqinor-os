"""ASTK14 (C-ASTK-002, S2) — garde de CLASSE « prix d'achat servi sans gate ».

Un test balaie, par INTROSPECTION des routeurs ``apps/stock/urls.py`` et
``apps/achats/urls.py`` (aucune liste manuelle de routes), toutes les routes GET
(list, retrieve et actions ``@action`` en lecture) avec un compte Commercial et
un compte Viewer (sans ``prix_achat_voir``) sur une société seedée, et échoue si
un JSON de réponse 200 contient une clé de prix ou de montant d'achat.

Routes exemptées par une règle NOMMÉE (réponse non JSON : PDF/XLSX/HTML), jamais
par numéro de ligne.

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
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, LigneFactureFournisseur,
    PaiementFournisseur, PalierPrixFournisseur, PrixFournisseur, Produit,
)
from authentication.models import Company

User = get_user_model()

RACINES = {
    'apps.stock.urls': '/api/django/stock/',
    'apps.achats.urls': '/api/django/achats/',
}
CLES_EXACTES = {
    'prix_achat', 'prix_unitaire_ht', 'prix_convenu', 'montant_achete',
    'frais_annexes', 'paiements',
}
PREFIXES_CLES = ('prix_achat_', 'total_achat')
RE_PK = re.compile(r'\(\?P<pk>[^)]*\)')


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
    return sorted(set(trouvees))


def balayer(api, routes):
    """GET de chaque route ; renvoie (violations, nb_json_200)."""
    ids = {}
    violations = []
    nb_json = 0
    # 1) listes d'abord : elles fournissent un pk réel par ressource.
    for url, kind in routes:
        if kind != 'list':
            continue
        reponse = api.get(url)
        if reponse.status_code == 200 and 'json' in (
                reponse.get('Content-Type') or ''):
            nb_json += 1
            donnees = reponse.json()
            lignes = donnees.get('results') if isinstance(donnees, dict) \
                else donnees
            if isinstance(lignes, list) and lignes \
                    and isinstance(lignes[0], dict) and 'id' in lignes[0]:
                ids[url] = lignes[0]['id']
            trouvees = cles_interdites(donnees)
            if trouvees:
                violations.append(f'GET {url} -> {sorted(trouvees)}')
    # 2) le reste.
    for url, kind in routes:
        if kind == 'list':
            continue
        if '{pk}' in url:
            prefixe = url.split('{pk}')[0]
            pk = ids.get(prefixe)
            if pk is None:
                continue
            cible = url.replace('{pk}', str(pk))
        else:
            cible = url
        reponse = api.get(cible)
        # Règle d'exemption nommée : réponse non JSON (PDF, XLSX, HTML).
        if reponse.status_code != 200 or 'json' not in (
                reponse.get('Content-Type') or ''):
            continue
        nb_json += 1
        trouvees = cles_interdites(reponse.json())
        if trouvees:
            violations.append(f'GET {cible} -> {sorted(trouvees)}')
    return violations, nb_json


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
            fournisseur=self.fournisseur)
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
            violations, nb_json = balayer(_api(utilisateur), routes)
            self.assertGreater(nb_json, 5, utilisateur.username)
            self.assertEqual(
                violations, [],
                f'{utilisateur.username} reçoit des clés de prix/montant '
                "d'achat :\n" + '\n'.join(violations))

    def test_controle_positif_administrateur(self):
        """L'Administrateur voit ces clés sur les mêmes données : la garde
        scanne donc un jeu de données qui en contient réellement."""
        violations, _ = balayer(_api(self.admin), routes_get())
        self.assertTrue(violations, "l'admin ne voit aucune clé d'achat : jeu "
                                    'de données vide ou garde aveugle')

    def test_le_detecteur_nomme_les_cles(self):
        """Test-du-test : le détecteur de clés repère chaque famille."""
        plante = {'results': [{'prix_achat': 1, 'x': {'prix_achat_devise': 2}},
                              {'total_achats_ht': 3, 'prix_convenu': 4,
                               'lignes': [{'frais_annexes': 5,
                                           'prix_unitaire_ht': 6}],
                               'paiements': [], 'montant_achete': 7}]}
        self.assertEqual(cles_interdites(plante), {
            'prix_achat', 'prix_achat_devise', 'total_achats_ht',
            'prix_convenu', 'frais_annexes', 'prix_unitaire_ht', 'paiements',
            'montant_achete'})
        self.assertEqual(cles_interdites({'quantite': 1, 'prix_vente': 2}),
                         set())
