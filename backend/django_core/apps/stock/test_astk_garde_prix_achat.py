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
from django.test import SimpleTestCase, TestCase
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
from apps.installations.models import (AppelCommande, ApprobationBCF, BudgetProjet, CommandeCadre,
                                       CommandeCadreLigne, ContratPrixFournisseur, ContratPrixLigne,
                                       DossierImport, FraisImport, LandedCostLigne, Projet)
from apps.stock.models_wms import UniteLogistique
from authentication.models import Company

User = get_user_model()

RACINES = {
    'apps.stock.urls': '/api/django/stock/',
    'apps.achats.urls': '/api/django/achats/',
    'apps.installations.urls': '/api/django/installations/',  # APFS29 — achats restés là
}
CLES_EXACTES = {
    'prix_achat', 'prix_unitaire_ht', 'prix_convenu', 'montant_achete',
    'frais_annexes', 'paiements', 'montant',
    # ERR-STK-PRIX-ACHAT-SUITE — valeurs de stock/pertes au coût d'achat.
    'total_valeur', 'valeur',
    # ASTK255 — motif chiffré du rapprochement 3 voies.
    'motif_ecart',
    'prix_negocie', 'valeur_fob', 'budget_materiel', 'budget_main_oeuvre',  # APFS29
    'budget_sous_traitance', 'budget_divers', 'budget_total',
    'marge', 'taux_pct', 'reste_categorie', 'reste_total',  # ALEC30 (C-ALEC-026)
}
PREFIXES_CLES = ('prix_achat_', 'total_achat', 'montant_', 'cout_')
RE_PK = re.compile(r'\(\?P<pk>[^)]*\)')
#: ERR-STK-PRIX-ACHAT-SUITE — chemins SIMPLES (hors routeur) balayés aussi.
CHEMINS_SIMPLES = ('/api/django/stock/tableau-bord-achats/',
                   '/api/django/stock/entrepot/pertes/',
                   '/api/django/stock/entrepot/cockpit/',  # ALEC30
                   '/api/django/installations/controle-budgetaire/')
#: ALEC30 — routes dont le correctif n'est pas sur `main` au build : leur fuite
#: est RAPPORTÉE sans faire échouer ; une entrée qui ne fuit plus fait échouer
#: la garde (la retirer). Gabarit de route → constat (tâche du correctif).
#: Vague 12 : ALEC3/7/8/9/11 ont livré leurs correctifs — plus aucune attente.
EN_ATTENTE = {}
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
    'interventions/suggestions-creation/': lambda t: {'type_intervention': 'installation'},
    'kits/{pk}/composition-au/': lambda t: {'date': t.aujourdhui},  # ALEC30
    'controle-budgetaire/': lambda t: {'montant': '0', 'projet': t.projet.id},
}


def cles_interdites(payload):
    """Ensemble des clés d'achat présentes (récursif). Une clé servie à
    ``null`` ne porte aucun montant : c'est le masque voulu (ALEC11,
    ``cout_total`` null sans ``prix_achat_voir``), pas une fuite."""
    trouvees = set()
    if isinstance(payload, dict):
        for cle, valeur in payload.items():
            if valeur is not None and (cle in CLES_EXACTES or cle.startswith(PREFIXES_CLES)):
                trouvees.add(cle)
            trouvees |= cles_interdites(valeur)
    elif isinstance(payload, list):
        for valeur in payload:
            trouvees |= cles_interdites(valeur)
    return trouvees


#: ATST4 — en-têtes d'achat d'un export XLSX (1re ligne de chaque feuille).
RE_ENTETES_ACHAT = re.compile(r"^(Coût|Valeur|Prix d'achat|Montant)", re.IGNORECASE)


def entetes_achat(contenu):
    """ATST4 — en-têtes d'achat (triés) de la ligne d'en-tête d'un classeur."""
    from io import BytesIO
    from openpyxl import load_workbook
    classeur = load_workbook(BytesIO(contenu), read_only=True)
    return sorted({str(c) for ws in classeur.worksheets
                   for c in next(ws.iter_rows(max_row=1, values_only=True), ())
                   if c and RE_ENTETES_ACHAT.match(str(c))})


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


def balayer(api, routes, utilisateur, fixtures=None, attendues=None):
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
        # ATST4 — un XLSX est OUVERT : sa ligne d'en-tête passe au détecteur.
        if 'spreadsheetml' in (reponse.get('Content-Type') or ''):
            if entetes := entetes_achat(reponse.content):
                violations.append(f'GET {cible} -> {entetes}')
            return None
        # Règle d'exemption nommée : réponse non JSON (PDF, HTML).
        if 'json' not in (reponse.get('Content-Type') or ''):
            return None
        nb_json += 1
        donnees = reponse.json()
        trouvees = cles_interdites(donnees)
        if trouvees:  # ALEC30 — une route EN_ATTENTE est rapportée à part.
            (attendues if attendues is not None and gabarit in EN_ATTENTE
             else violations).append(f'GET {cible} -> {sorted(trouvees)}  [{gabarit}]')
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
        expedition = creer_expedition_transporteur(
            company=self.company, unite=self.unite, cout_reel=Decimal('180'))
        # ALEC30 — l'expédition est DU JOUR (cockpit), un kit à composant (et sa
        # révision), une approbation de BCF et un budget de programme.
        from django.utils import timezone
        from apps.stock.models import KitComposant, KitProduit
        from apps.stock.services import snapshot_revision_kit
        type(expedition).objects.filter(pk=expedition.pk).update(date_expedition=timezone.now())
        self.aujourdhui = timezone.localdate().isoformat()
        kit = KitProduit.objects.create(company=self.company, nom='Kit ALEC30', sku='KIT-ALEC30')
        KitComposant.objects.create(kit=kit, produit=self.produit, quantite=2)
        snapshot_revision_kit(kit)
        ApprobationBCF.objects.create(company=self.company, bcf=bcf, palier='responsable',
                                      montant_approuve=Decimal('10000'))
        self.projet = Projet.objects.create(company=self.company, reference='PRJ-ALEC30', nom='Programme')
        BudgetProjet.objects.create(company=self.company, projet=self.projet, budget_materiel=Decimal('50000'))
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=datetime.date(2026, 9, 2), cout_impact_mad=Decimal('300'))
        AccordRFAFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            periode_debut=datetime.date(2026, 1, 1),
            periode_fin=datetime.date(2026, 12, 31),
            seuil_ca_achat=Decimal('5000'), montant_fixe=Decimal('400'))
        contrat = ContratPrixFournisseur.objects.create(  # APFS29 — achats du routeur installations
            company=self.company, reference='CPF-APFS29', intitule='Accord',
            fournisseur=self.fournisseur, statut='actif')
        ContratPrixLigne.objects.create(
            contrat=contrat, produit=self.produit, prix_convenu=Decimal('1200'))
        cadre = CommandeCadre.objects.create(
            company=self.company, reference='CC-APFS29', intitule='Cadre',
            fournisseur=self.fournisseur)
        AppelCommande.objects.create(
            company=self.company, quantite=2, ligne=CommandeCadreLigne.objects.create(
                commande_cadre=cadre, produit=self.produit, prix_negocie=Decimal('1100')))
        dossier = DossierImport.objects.create(
            company=self.company, reference='IMP-APFS29', designation='Conteneur')
        FraisImport.objects.create(
            company=self.company, dossier=dossier, categorie='fret', montant=Decimal('600'))
        LandedCostLigne.objects.create(
            company=self.company, dossier=dossier, produit=self.produit,
            quantite=10, valeur_fob=Decimal('8000'))
        # ATST4 — un inventaire FIGÉ (exercice clos) : liste, détail et XLSX atteints.
        from apps.stock.services import figer_inventaire_annuel
        figer_inventaire_annuel(self.company, 2025, self.admin)

    def test_introspection_non_vide(self):
        """Le balayage découvre bien les routes (garde contre une
        introspection silencieusement vide)."""
        routes = routes_get()
        self.assertGreater(len(routes), 40, routes)
        urls = {u for u, _ in routes}
        self.assertTrue(any('bons-commande-fournisseur' in u for u in urls))
        self.assertTrue(any('factures-fournisseur' in u for u in urls))

    def test_aucune_route_ne_sert_de_prix(self):
        routes, attendues = routes_get(), []
        for utilisateur in (self.commercial, self.viewer):
            violations, nb_json, erreurs = balayer(
                _api(utilisateur), routes, utilisateur, self, attendues)
            self.assertGreater(nb_json, 5, utilisateur.username)
            self.assertEqual(
                violations, [],
                f'{utilisateur.username} reçoit des clés de prix/montant '
                "d'achat :\n" + '\n'.join(violations))
            self.assertEqual(erreurs, [], f'{utilisateur.username} : réponses '
                             'non-200 du balayage :\n' + '\n'.join(erreurs))
        if attendues:  # ALEC30 — rapportées, jamais muettes.
            print('\nGarde prix d\'achat — fuites EN_ATTENTE :\n' + '\n'.join(attendues))
        rapportees = {ligne.rsplit('[', 1)[-1].rstrip(']') for ligne in attendues}
        self.assertEqual(sorted(set(EN_ATTENTE) - rapportees), [],
                         "entrée d'EN_ATTENTE qui ne fuit plus : la retirer")

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

    def test_palier_admin_sans_prix_achat_voir_rapports_masques(self):
        """STK1 (D-ASTK-2 / D-W2-Q6) — les rapports produit gardés par le seul
        palier administrateur retirent leurs valeurs d'achat pour un rôle
        administrateur SANS `prix_achat_voir` (mêmes lignes, quantités
        gardées) ; l'Administrateur qui porte le droit reçoit tout, inchangé."""
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=12, seuil_alerte=20)
        perms = [c for c in dict(CANONICAL_SYSTEM_ROLES)['Administrateur'] if c != 'prix_achat_voir']
        sans = User.objects.create_user(
            username='astk14-admin-sans-prix', password='x', company=self.company,
            role=Role.objects.create(company=self.company, nom='Admin sans prix', permissions=perms))
        self.assertEqual((sans.is_admin_role, sans.can_view_buy_prices), (True, False))
        masquees = {'total', 'valeur', 'cout_moyen', 'prix_achat', 'valeur_stock', 'valeur_totale'}

        def cles(donnees):
            if isinstance(donnees, dict):
                return set(donnees).union(*(cles(v) for v in donnees.values()))
            return set().union(*(cles(v) for v in donnees)) if isinstance(donnees, list) else set()
        base = '/api/django/stock/produits/'
        routes = {'valorisation/': ({}, {'total', 'valeur', 'cout_moyen'}),
                  'valorisation-a-date/': ({'date': self.aujourdhui}, {'total'}),
                  'a-reapprovisionner/': ({}, {'prix_achat'}),
                  'rotation/': ({}, {'valeur_stock'}),
                  f'{self.produit.id}/comparer-fournisseurs/': ({}, {'prix_achat'}),
                  'previsions-reappro/': ({}, set()), 'rapport-pertes/': ({}, set())}
        servis = {}
        for suffixe, (params, achat) in routes.items():
            plein, masque = (_api(u).get(base + suffixe, params) for u in (self.admin, sans))
            self.assertEqual((plein.status_code, masque.status_code), (200, 200), suffixe)
            self.assertLessEqual(achat, cles(plein.json()), suffixe)
            self.assertEqual(cles(masque.json()) & masquees, set(), suffixe)
            self.assertEqual(cles_interdites(masque.json()), set(), suffixe)
            servis[suffixe] = masque.json()
        self.assertEqual(servis['valorisation/']['lignes'][0]['quantite'], 12)
        self.assertEqual([(r['produit_id'], r['fournisseur_id']) for r in servis['a-reapprovisionner/']],
                         [(self.produit.id, self.fournisseur.id)])
        self.assertEqual(servis[f'{self.produit.id}/comparer-fournisseurs/'][0]['fournisseur_id'],
                         self.fournisseur.id)
        export = base + 'valorisation-xlsx/'
        self.assertEqual(entetes_achat(_api(sans).get(export).content), [])
        self.assertEqual(entetes_achat(_api(self.admin).get(export).content),
                         ['Coût moyen (HT)', 'Valeur (HT)'])

    def test_controle_positif_administrateur(self):
        """L'Administrateur voit ces clés sur les mêmes données : la garde
        scanne donc un jeu de données qui en contient réellement."""
        violations, _, _ = balayer(
            _api(self.admin), routes_get(), self.admin, self)
        self.assertTrue(violations, "l'admin ne voit aucune clé d'achat : jeu "
                                    'de données vide ou garde aveugle')
        texte = '\n'.join(violations)  # ATST4 — inventaire valorisé + XLSX vus
        self.assertRegex(texte, r'inventaires-annuels/ -> .*total_valeur')
        self.assertIn('Coût moyen (HT)', texte)

    def test_serialiseurs_achat_installations_masques(self):
        """APFS29 — chaque sérialiseur d'achat d'`installations` masque toute clé d'achat déclarée."""
        from apps.installations import serializers as ser
        from apps.stock.permissions import MasqueMontantsAchatMixin
        for nom in ('ContratPrixLigne', 'CommandeCadreLigne', 'AppelCommande', 'FraisImport',
                    'LandedCostLigne', 'Livraison', 'OrdreAssemblage', 'BudgetProjet'):
            classe = getattr(ser, f'{nom}Serializer')
            self.assertTrue(issubclass(classe, MasqueMontantsAchatMixin), nom)
            # Valeur NON nulle : le détecteur ignore une clé servie à null (ALEC30).
            declarees = cles_interdites({c: 1 for c in classe.Meta.fields})
            self.assertTrue(declarees, nom)
            self.assertLessEqual(declarees, set(classe.champs_montants_achat), nom)
        url = '/api/django/installations/contrats-prix-fournisseur/prix-convenu/'
        self.assertEqual(_api(self.commercial).get(url, {'produit': self.produit.id}).status_code, 403)
        rep = _api(self.admin).get(url, {'produit': self.produit.id})
        self.assertEqual((rep.status_code, rep.json()['prix_convenu']), (200, 1200.0))

    def test_le_detecteur_nomme_les_cles(self):
        """Test-du-test : le détecteur de clés repère chaque famille."""
        plante = {'results': [{'prix_achat': 1, 'x': {'prix_achat_devise': 2}},
                              {'total_achats_ht': 3, 'prix_convenu': 4,
                               'lignes': [{'frais_annexes': 5,
                                           'prix_unitaire_ht': 6}],
                               'paiements': [], 'montant_achete': 7,
                               'montant_total': 8, 'cout_retard': 9,
                               'montant': 10, 'marge': 11, 'taux_pct': 12,
                               'reste_categorie': 13, 'reste_total': 14}]}
        self.assertEqual(cles_interdites(plante), {
            'prix_achat', 'prix_achat_devise', 'total_achats_ht',
            'prix_convenu', 'frais_annexes', 'prix_unitaire_ht', 'paiements',
            'montant_achete', 'montant_total', 'cout_retard', 'montant',
            'marge', 'taux_pct', 'reste_categorie', 'reste_total'})
        self.assertEqual(cles_interdites({'quantite': 1, 'prix_vente': 2}),
                         set())
        from io import BytesIO
        from openpyxl import Workbook
        classeur, flux = Workbook(), BytesIO()
        classeur.active.append(['Produit', 'Quantité', 'Coût moyen (HT)'])
        classeur.save(flux)
        self.assertEqual(entetes_achat(flux.getvalue()), ['Coût moyen (HT)'])
        # ALEC11 — masque à null : rien de servi ; 0 reste un montant nommé.
        self.assertEqual(cles_interdites({'cout_total': None}), set())
        self.assertEqual(cles_interdites({'cout_total': 0}), {'cout_total'})


def cles_prix_vente(payload):
    """D-ACAL-152 — clés de prix de VENTE servies avec une valeur (récursif)."""
    from apps.stock.permissions import PRIX_VENTE_CHAMPS
    trouvees = set()
    if isinstance(payload, dict):
        for cle, valeur in payload.items():
            if valeur is not None and cle in PRIX_VENTE_CHAMPS:
                trouvees.add(cle)
            trouvees |= cles_prix_vente(valeur)
    elif isinstance(payload, list):
        for valeur in payload:
            trouvees |= cles_prix_vente(valeur)
    return trouvees


class MasquePrixVenteSansBase(SimpleTestCase):
    """CI #1564 api-fuzz — le masque D-ACAL-152 d'une RÉPONSE ne déclenche jamais
    l'authentification (``stock/produits/0.5/`` répondait 500 au lieu de 404)."""

    def _vue(self):
        from apps.stock.permissions import MasquePrixVenteReponseMixin

        class Base:
            def finalize_response(self, request, response, *args, **kwargs):
                return response

        class Vue(MasquePrixVenteReponseMixin, Base):
            pass

        return Vue()

    def test_reponse_avant_authentification_inchangee_sans_lire_user(self):
        from rest_framework.response import Response

        class RequeteNonAuthentifiee:
            @property
            def user(self):
                raise AssertionError('authentification déclenchée par le masque')

        erreur = Response({'detail': 'Non trouvé.'}, status=404)
        self.assertIs(self._vue().finalize_response(RequeteNonAuthentifiee(), erreur), erreur)
        self.assertEqual(erreur.data, {'detail': 'Non trouvé.'})

    def test_utilisateur_deja_authentifie_sans_le_droit_perd_les_prix(self):
        from types import SimpleNamespace

        from rest_framework.response import Response

        def requete(voit):
            return SimpleNamespace(_user=SimpleNamespace(is_authenticated=True, can_view_sale_prices=voit))

        masquee = Response({'nom': 'Panneau', 'prix_vente': '1500'}, status=200)
        self._vue().finalize_response(requete(False), masquee)
        self.assertEqual(masquee.data, {'nom': 'Panneau'})
        entiere = Response({'nom': 'Panneau', 'prix_vente': '1500'}, status=200)
        self._vue().finalize_response(requete(True), entiere)
        self.assertEqual(entiere.data, {'nom': 'Panneau', 'prix_vente': '1500'})


class MasqueAchatRapportsSansBase(SimpleTestCase):
    """Lot 9 — le masque d'achat des rapports produit ne déclenche jamais
    l'authentification sur une réponse d'erreur (jumeau de MasquePrixVenteSansBase)."""

    def _vue(self, action='valorisation'):
        from apps.stock.permissions import MasqueAchatRapportsProduitMixin

        class Base:
            def finalize_response(self, request, response, *args, **kwargs):
                return response

        class Vue(MasqueAchatRapportsProduitMixin, Base):
            pass

        vue = Vue()
        vue.action = action
        return vue

    def test_reponse_erreur_inchangee_sans_lire_user(self):
        from rest_framework.response import Response

        class RequeteNonAuthentifiee:
            @property
            def user(self):
                raise AssertionError('authentification déclenchée par le masque')

        erreur = Response({'detail': 'Non authentifié.', 'total': 1}, status=401)
        erreur.exception = True
        self.assertIs(self._vue().finalize_response(RequeteNonAuthentifiee(), erreur), erreur)
        self.assertEqual(erreur.data, {'detail': 'Non authentifié.', 'total': 1})

    def test_utilisateur_deja_authentifie_sans_le_droit_perd_les_prix_achat(self):
        from types import SimpleNamespace

        from rest_framework.response import Response

        def requete(voit):
            return SimpleNamespace(_user=SimpleNamespace(
                is_authenticated=True, portee='interne', can_view_buy_prices=voit))

        masquee = Response({'total': 10, 'valeur': 5, 'nom': 'x'}, status=200)
        self._vue().finalize_response(requete(False), masquee)
        self.assertEqual(masquee.data, {'nom': 'x'})
        entiere = Response({'total': 10, 'valeur': 5, 'nom': 'x'}, status=200)
        self._vue().finalize_response(requete(True), entiere)
        self.assertEqual(entiere.data, {'total': 10, 'valeur': 5, 'nom': 'x'})


class GardePrixVente(TestCase):
    """D-ACAL-152 (fondateur, 26/11/2026) — Technicien et Technicien
    responsable (sans ``prix_vente_voir``) ne reçoivent AUCUN prix de vente du
    stock : liste, détail, recherche, kits imbriqués, explosion, structure,
    export XLSX, étiquettes prix, catalogue B2B ; l'Administrateur les reçoit
    tous, comme avant. Balayage des routes GET de ``apps.stock.urls``."""

    def setUp(self):
        from apps.stock.models import KitComposant, KitProduit
        self.company = Company.objects.create(nom='DACAL152', slug='dacal152-stock')
        perms = dict(CANONICAL_SYSTEM_ROLES)

        def _role_user(nom):
            role = Role.objects.create(company=self.company, nom=nom, permissions=perms[nom])
            return User.objects.create_user(
                username=f'dacal152-{nom.lower().replace(" ", "-")}', password='x',
                company=self.company, role=role)

        self.tech = _role_user('Technicien')
        self.chef = _role_user('Technicien responsable')
        self.admin = _role_user('Administrateur')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau DACAL152', sku='D152-1',
            prix_vente=Decimal('1500'), prix_achat=Decimal('900'),
            prix_fixe_ht=Decimal('100'), prix_par_panneau_ht=Decimal('10'),
            paliers_prix_vente=[{'seuil_min': 1, 'seuil_max': None, 'prix_vente_ttc': '1700.00'}],
            louable=True, tarif_location_jour=Decimal('50'))
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit D152', sku='KD152')
        KitComposant.objects.create(kit=self.kit, produit=self.produit, quantite=Decimal('2'))

    def _urls_json(self):
        p, k = self.produit.id, self.kit.id
        return ['/api/django/stock/produits/', f'/api/django/stock/produits/{p}/',
                '/api/django/stock/produits/?search=DACAL152',
                '/api/django/stock/kits/', f'/api/django/stock/kits/{k}/',
                f'/api/django/stock/kits/{k}/exploser/', f'/api/django/stock/kits/{k}/structure/',
                '/api/django/stock/catalogue-b2b/']

    def test_technicien_sans_aucun_prix_de_vente(self):
        self.assertEqual((self.tech.can_view_sale_prices, self.chef.can_view_sale_prices,
                          self.admin.can_view_sale_prices), (False, False, True))
        for user in (self.tech, self.chef):
            api = _api(user)
            for url in self._urls_json():
                rep = api.get(url)
                self.assertEqual(rep.status_code, 200, (user.username, url))
                donnees = rep.json()
                self.assertEqual(cles_prix_vente(donnees), set(), (user.username, url))
                if url.endswith('catalogue-b2b/'):
                    self.assertNotIn('prix', donnees['produits'][0])
            # Le reste du produit est servi (stock, nom) : le flux technicien marche.
            detail = api.get(f'/api/django/stock/produits/{self.produit.id}/').json()
            self.assertEqual((detail['nom'], detail['quantite_stock']), ('Panneau DACAL152', 0))
            rep = api.get('/api/django/stock/produits/etiquettes-prix/',
                          {'ids': self.produit.id, 'sortie': 'html'})
            self.assertEqual(rep.status_code, 403, user.username)
            self.assertIn('prix_vente_voir', str(rep.data['detail']))

    def test_administrateur_garde_tous_les_prix(self):
        from apps.stock.permissions import PRIX_VENTE_CHAMPS
        api = _api(self.admin)
        detail = api.get(f'/api/django/stock/produits/{self.produit.id}/').json()
        champs = {c for c in PRIX_VENTE_CHAMPS if c in detail}
        self.assertEqual(champs, {'prix_vente', 'paliers_prix_vente', 'prix_fixe_ht',
                                  'prix_par_panneau_ht', 'tarif_location_jour',
                                  'tarif_location_semaine', 'tarif_location_mois'})
        self.assertEqual(Decimal(str(detail['prix_vente'])), Decimal('1500'))
        kit = api.get(f'/api/django/stock/kits/{self.kit.id}/').json()
        self.assertEqual(Decimal(str(kit['composants'][0]['prix_vente'])), Decimal('1500'))
        lignes = api.get(f'/api/django/stock/kits/{self.kit.id}/exploser/').json()['lignes']
        self.assertIn('prix_vente_unitaire', lignes[0])
        self.assertIn('prix_vente_total', api.get(f'/api/django/stock/kits/{self.kit.id}/structure/').json())
        self.assertIn('prix', api.get('/api/django/stock/catalogue-b2b/').json()['produits'][0])
        rep = api.get('/api/django/stock/produits/etiquettes-prix/',
                      {'ids': self.produit.id, 'sortie': 'html'})
        self.assertEqual(rep.status_code, 200)

    def test_export_xlsx_sans_colonne_prix_pour_le_technicien_responsable(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from apps.stock.services import PRODUCT_EXPORT_HEADERS

        def entetes(user):
            rep = _api(user).post('/api/django/stock/produits/export-xlsx/',
                                  {'ids': [self.produit.id]}, format='json')
            self.assertEqual(rep.status_code, 200, user.username)
            feuille = load_workbook(BytesIO(rep.content), read_only=True).active
            return [list(r) for r in feuille.iter_rows(max_row=2, values_only=True)]

        admin = entetes(self.admin)
        self.assertEqual(admin[0], PRODUCT_EXPORT_HEADERS)  # inchangé avec le droit
        self.assertIn('1500.00', admin[1])
        chef = entetes(self.chef)  # stock_export, sans prix_vente_voir
        self.assertEqual(chef[0], [h for h in PRODUCT_EXPORT_HEADERS if h != 'Prix vente HT'])
        self.assertNotIn('1500.00', chef[1])

    def test_ecriture_inchangee_prix_vide_du_formulaire_sans_effet(self):
        """Le Technicien responsable (stock_modifier, ni catalogue_prix_modifier
        ni prix_vente_voir) : son formulaire, servi sans prix, renvoie des prix
        VIDES → le seuil est écrit, aucun prix ne bouge ; changer un prix reste
        le 403 d'ASTK20 (contrat d'écriture inchangé)."""
        url = f'/api/django/stock/produits/{self.produit.id}/'
        api = _api(self.chef)
        rep = api.patch(url, {'seuil_alerte': 3, 'prix_vente': '', 'prix_fixe_ht': None,
                              'paliers_prix_vente': []}, format='json')
        self.assertEqual(rep.status_code, 200, getattr(rep, 'data', ''))
        self.assertEqual(cles_prix_vente(rep.json()), set())
        self.produit.refresh_from_db()
        self.assertEqual((self.produit.seuil_alerte, self.produit.prix_vente,
                          self.produit.prix_fixe_ht), (3, Decimal('1500'), Decimal('100')))
        self.assertEqual(len(self.produit.paliers_prix_vente), 1)
        rep = api.patch(url, {'prix_vente': '1'}, format='json')
        self.assertEqual(rep.status_code, 403, getattr(rep, 'data', ''))
        self.assertIn('catalogue_prix_modifier', str(rep.data['detail']))
        # D-ACAL-165 — un tarif de location qu'il ne voit pas : vide = sans effet,
        # non vide = 403 « prix_vente_voir » (avant : ÉCRIT, puis masqué en lecture).
        rep = api.patch(url, {'tarif_location_jour': '', 'tarif_location_mois': None}, format='json')
        self.assertEqual(rep.status_code, 200, getattr(rep, 'data', ''))
        rep = api.patch(url, {'tarif_location_jour': '1'}, format='json')
        self.assertEqual(rep.status_code, 403, getattr(rep, 'data', ''))
        self.assertIn('prix_vente_voir', str(rep.data['detail']))
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.tarif_location_jour, Decimal('50'))
        # Avec le droit : l'écriture du tarif est inchangée.
        rep = _api(self.admin).patch(url, {'tarif_location_jour': '55'}, format='json')
        self.assertEqual(rep.status_code, 200, getattr(rep, 'data', ''))
        self.assertEqual(Decimal(str(rep.json()['tarif_location_jour'])), Decimal('55'))

    def test_balayage_des_routes_stock_sans_aucun_montant_de_vente(self):
        """Garde de CLASSE, par les VALEURS (D-ACAL-165) : un prix de vente et
        un total de devis REPÉRABLES sont semés ; aucune réponse d'aucune route
        GET de ``apps.stock.urls`` lue par le Technicien ou le Technicien
        responsable ne les contient, sous quelque nom de clé que ce soit. Le
        corps de TOUTE réponse est scanné (non-200 compris, XLSX ouvert) ; les
        routes non-200 et les gabarits de détail sans objet sont NOMMÉS dans
        le message, jamais sautés en silence."""
        from io import BytesIO

        from openpyxl import load_workbook

        from apps.crm.models import Client
        from apps.ventes.models import Devis, LigneDevis
        Produit.objects.filter(pk=self.produit.pk).update(
            prix_vente=Decimal('98765.43'), prix_fixe_ht=Decimal('87654.32'),
            prix_par_panneau_ht=Decimal('76543.21'), tarif_location_jour=Decimal('65432.19'),
            paliers_prix_vente=[{'seuil_min': 1, 'seuil_max': None, 'prix_vente_ttc': '54321.98'}])
        client = Client.objects.create(company=self.company, nom='Client D165', prenom='',
                                       email='d165@example.com', telephone='+212600000165')
        devis = Devis.objects.create(company=self.company, reference='DEV-D165-1', client=client,
                                     created_by=self.admin, statut=Devis.Statut.ENVOYE,
                                     taux_tva=Decimal('20'))
        LigneDevis.objects.create(devis=devis, produit=self.produit, designation='Panneau D165',
                                  quantite=Decimal('3'), prix_unitaire=Decimal('98765.43'))
        devis.refresh_from_db()
        aiguilles = ['98765.4', '87654.3', '76543.2', '65432.1', '54321.9', '118518.5']
        if devis.total_ttc:
            aiguilles.append(str(devis.total_ttc).split('.')[0])
        # Contrôle positif : l'Administrateur LIT bien ces valeurs (garde non aveugle).
        admin = _api(self.admin).get(f'/api/django/stock/produits/{self.produit.id}/')
        self.assertIn('98765.4', admin.content.decode('utf-8'))
        routes = [(u, k) for u, k in routes_get() if u.startswith('/api/django/stock/')]

        def texte(rep):
            if 'spreadsheetml' in (rep.get('Content-Type') or ''):
                classeur = load_workbook(BytesIO(rep.content), read_only=True)
                return ' '.join(str(c) for ws in classeur.worksheets
                                for ligne in ws.iter_rows(values_only=True) for c in ligne)
            return rep.content.decode('utf-8', 'replace')

        for user in (self.tech, self.chef):
            api, ids, fuites, non_200, sans_objet = _api(user), {}, [], [], []
            for url, kind in sorted(routes, key=lambda r: r[1] != 'list'):
                pk = ids.get(url.split('{pk}')[0]) if '{pk}' in url else ''
                if pk is None:
                    sans_objet.append(url)
                    continue
                rep = api.get(url.replace('{pk}', str(pk)))
                corps = texte(rep)
                if trouvees := [a for a in aiguilles if a in corps]:
                    fuites.append(f'GET {url} (HTTP {rep.status_code}) -> {trouvees}')
                if rep.status_code != 200:
                    non_200.append(f'{url} -> HTTP {rep.status_code}')
                    continue
                if kind == 'list' and 'json' in (rep.get('Content-Type') or ''):
                    donnees = rep.json()
                    lignes = donnees.get('results') if isinstance(donnees, dict) else donnees
                    if isinstance(lignes, list) and lignes and isinstance(lignes[0], dict):
                        ids[url] = lignes[0].get('id')
            rapport = (f'\n{user.username} — non-200 ({len(non_200)}) : ' + '; '.join(non_200)
                       + f'\nsans objet ({len(sans_objet)}) : ' + '; '.join(sans_objet))
            print(rapport)
            self.assertEqual(fuites, [], '\n'.join(fuites) + rapport)
            self.assertGreater(len(routes) - len(non_200) - len(sans_objet), 5, rapport)
