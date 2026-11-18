"""TCH15 — toutes les routes de l'app `taches` déclarées, gardées, et pas encore construites.

Sans base (SimpleTestCase) : les 106 couples méthode × chemin de reference/api.md §3 résolvent,
chaque chemin sert EXACTEMENT ses méthodes, chaque vue lève `PasEncore` (501) et porte la
permission STRICTE ; `est_assistant`, la permission et le bouchon des routes à jeton.
Avec base (TestCase, CI) : 403 sans `taches_voir` pour tout compte (y compris un compte hérité
« responsable » sans rôle fin), 501 avec, 401 neutre sur capture, flux et tuile.
"""
import datetime
import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken
from testkit.time import frozen

from apps.roles.models import Role
from apps.taches.tests import fabriques
from apps.taches.views.base import (
    AUTH_JETON, JetonPasEncoreLivre, PasEncore, PermissionTaches, est_assistant,
)

PREFIXE = '/api/django/taches/'
API_MD = Path(__file__).resolve().parents[5] / 'docs' / 'taches' / 'reference' / 'api.md'
METHODES_HTTP = ('get', 'post', 'put', 'patch', 'delete')

#: reference/api.md §3 — les 106 couples, dans l'ordre des tableaux.
ROUTES_TEXTE = """
GET aujourdhui/
GET aujourdhui/ailleurs/
GET badge/
POST vu/
GET journee/proposition/
GET journee/priorites/
GET journee/point/
POST journee/planifier/
POST journee/essentiel/
POST journee/alleger/
GET journee/cloture/
POST journee/cloturer/
GET agenda/
GET recherche/
POST saisie-rapide/
POST capture/
GET taches/
POST taches/
GET taches/{id}/
PATCH taches/{id}/
DELETE taches/{id}/
POST taches/{id}/planifier/
POST taches/{id}/terminer/
POST taches/{id}/rouvrir/
POST taches/{id}/trancher/
POST taches/{id}/sauter/
POST taches/{id}/attendre/
POST taches/{id}/recu/
POST taches/{id}/reordonner/
POST taches/{id}/restaurer/
POST taches/{id}/rappels/
POST taches/{id}/changement/apercu/
POST taches/lot/
POST taches/lier-activite/
POST convertir-activite/
DELETE rappels/{id}/
POST rappels/{id}/repeter/
PATCH recurrences/{id}/
POST checklist/
PATCH checklist/{id}/
DELETE checklist/{id}/
POST checklist/{id}/reordonner/
GET etiquettes/
POST etiquettes/
PATCH etiquettes/{id}/
DELETE etiquettes/{id}/
GET vues/
POST vues/
PATCH vues/{id}/
DELETE vues/{id}/
GET supprimees/
GET gestes/
POST gestes/{id}/annuler/
GET suggestions/
POST suggestions/{id}/accepter/
POST suggestions/{id}/refuser/
GET projets/
POST projets/
GET projets/{id}/
PATCH projets/{id}/
DELETE projets/{id}/
POST projets/{id}/reordonner/
POST projets/trier-par-priorite/
GET projets/{id}/vue/
POST projets/{id}/planification/apercu/
POST projets/{id}/planification/
POST projets/{id}/decaler/
POST projets/{id}/terminer/
POST projets/{id}/rouvrir/
POST projets/{id}/restaurer/
POST projets/{id}/dupliquer/
POST projets/{id}/enregistrer-modele/
POST sections/
PATCH sections/{id}/
DELETE sections/{id}/
POST sections/{id}/reordonner/
GET modeles/
GET modeles/{id}/
PATCH modeles/{id}/
DELETE modeles/{id}/
POST modeles/{id}/instancier/
GET revue/projets/
PUT revue/projets/{projet_id}/
GET rythme/
POST rythme/
POST rythme/propositions/{id}/repondre/
POST preferences/
DELETE preferences/{cle}/
GET reglages/
PATCH reglages/
GET reglages-societe/
PATCH reglages-societe/
GET jetons/
POST jetons/
POST jetons/{id}/revoquer/
POST mon-iphone/test-notification/
GET tuile/
GET flux/{jeton}.ics
GET coach/entete/
GET mes-donnees/
POST tout-effacer/
GET agendas-externes/
POST agendas-externes/
PATCH agendas-externes/{id}/
DELETE agendas-externes/{id}/
POST agendas-externes/{id}/rafraichir/
"""
ROUTES = [tuple(ligne.split(' ', 1)) for ligne in ROUTES_TEXTE.strip().splitlines()]
#: Routes à jeton (J:x) : authentifiées par le bouchon tant que le jeton n'est pas livré.
ROUTES_A_JETON = {('POST', 'capture/'), ('GET', 'tuile/'), ('GET', 'flux/{jeton}.ics')}
#: Routes réservées à un administrateur (`IsAdminRole`).
ROUTES_ADMIN = {('GET', 'reglages-societe/'), ('PATCH', 'reglages-societe/')}
VALEURS = {'{id}': '7', '{projet_id}': '3', '{cle}': 'heure_limite', '{jeton}': 'tqf_abcdef'}


def concret(chemin):
    """Le chemin réel d'un gabarit (`taches/{id}/` → `/api/django/taches/taches/7/`)."""
    for gabarit, valeur in VALEURS.items():
        chemin = chemin.replace(gabarit, valeur)
    return PREFIXE + chemin


def est_construite(methode, chemin):
    """Vrai quand la méthode de la vue n'est plus le bouchon `raise PasEncore()` (route construite par sa
    tâche) : les tests « pas encore » ne regardent que les routes qui restent à construire."""
    vue = resolve(concret(chemin)).func.view_class
    return 'raise PasEncore()' not in inspect.getsource(getattr(vue, methode.lower()))


def methodes_par_chemin():
    par_chemin = {}
    for methode, chemin in ROUTES:
        par_chemin.setdefault(chemin, set()).add(methode.lower())
    return par_chemin


def couples_d_api_md():
    """Les couples des tableaux de §3 d'api.md (`GET` | `/api/django/taches/x/?q=`)."""
    texte = API_MD.read_text(encoding='utf-8')
    section = texte.split('## 3. Toutes les routes', 1)[1].split('## 4.', 1)[0]
    couples = set()
    for ligne in re.finditer(r'^\| (GET|POST|PUT|PATCH|DELETE) \| `([^`]+)`', section, re.MULTILINE):
        chemin = ligne.group(2).split('?', 1)[0].removeprefix(PREFIXE)
        couples.add((ligne.group(1), chemin))
    return couples


class RoutesSansBaseTests(SimpleTestCase):
    def test_106_couples_distincts(self):
        self.assertEqual(len(ROUTES), 106)
        self.assertEqual(len(set(ROUTES)), 106)

    def test_table_conforme_a_api_md(self):
        # docs/ est présent là où tournent les tests (patron de crm/tests_cad163_objectif_sans_8221.py).
        self.assertEqual(set(ROUTES), couples_d_api_md())

    def test_chaque_couple_resout_vers_une_vue_qui_sert_la_methode(self):
        for methode, chemin in ROUTES:
            with self.subTest(methode=methode, chemin=chemin):
                vue = resolve(concret(chemin)).func.view_class
                self.assertTrue(callable(getattr(vue, methode.lower(), None)))

    def test_chaque_chemin_sert_exactement_ses_methodes(self):
        for chemin, methodes in methodes_par_chemin().items():
            with self.subTest(chemin=chemin):
                vue = resolve(concret(chemin)).func.view_class
                servies = {m for m in METHODES_HTTP if callable(getattr(vue, m, None))}
                self.assertEqual(servies, methodes)

    def test_monte_aussi_sous_api_v1(self):
        self.assertEqual(resolve('/api/v1/taches/aujourdhui/').func.view_class,
                         resolve(concret('aujourdhui/')).func.view_class)

    def test_chaque_vue_porte_la_permission_stricte(self):
        for methode, chemin in ROUTES:
            with self.subTest(methode=methode, chemin=chemin):
                vue = resolve(concret(chemin)).func.view_class
                self.assertIn(PermissionTaches, vue.permission_classes)
                jeton = (methode, chemin) in ROUTES_A_JETON
                self.assertEqual(list(vue.authentication_classes) == AUTH_JETON, jeton)

    def test_chaque_vue_leve_pas_encore(self):
        for methode, chemin in ROUTES:
            if est_construite(methode, chemin):
                continue
            with self.subTest(methode=methode, chemin=chemin):
                correspondance = resolve(concret(chemin))
                vue = correspondance.func.view_class()
                with self.assertRaises(PasEncore):
                    getattr(vue, methode.lower())(None, **correspondance.kwargs)

    def test_pas_encore_rend_501(self):
        self.assertEqual(PasEncore.status_code, 501)
        self.assertEqual(PasEncore().get_codes(), 'pas_encore')


#: Modules de vues dont chaque opération porte son schéma complet (TCH145-TCH147).
MODULES_SCHEMATISES = ('journee', 'agenda', 'saisie', 'taches', 'erp', 'projets', 'rythme', 'reglages',
                       'presence', 'donnees', 'agenda_externe')
#: Échantillons qui ne sont la réponse ENTIÈRE d'aucune route : sous-objet d'une autre réponse
#: (ITEM d'une liste paginée, carte du moment, rendez-vous, proposition), formes d'erreur, ou
#: carte de fichier (gabarits des liens).
ECHANTILLONS_PARTIELS = {'item', 'carte_du_moment', 'rendez_vous', 'proposition', 'erreurs', 'liens_cibles'}
ECHANTILLONS = Path(__file__).resolve().parents[1] / 'contract_samples'


def generer_schema():
    """(schéma OpenAPI des seules routes `taches`, messages du générateur) — sans base."""
    from django.urls import include, path
    from drf_spectacular.drainage import GENERATOR_STATS
    from drf_spectacular.generators import SchemaGenerator

    with GENERATOR_STATS.silence():
        GENERATOR_STATS.reset()
        generateur = SchemaGenerator(patterns=[path('api/django/taches/', include('apps.taches.urls'))])
        schema = generateur.get_schema(request=None, public=True)
        messages = [*GENERATOR_STATS._warn_cache, *GENERATOR_STATS._error_cache]
        GENERATOR_STATS.reset()
    return schema, messages


def module_de(chemin):
    return resolve(concret(chemin)).func.view_class.__module__.rsplit('.', 1)[-1]


class SchemaTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema, cls.messages = generer_schema()
        cls.couverts = [(m, c) for m, c in ROUTES if module_de(c) in MODULES_SCHEMATISES]

    def _operation(self, methode, chemin):
        return self.schema['paths'][PREFIXE + chemin][methode.lower()]

    def _proprietes(self, contenu):
        schema = (contenu or {}).get('schema', {})
        if '$ref' in schema:
            schema = self.schema['components']['schemas'][schema['$ref'].rsplit('/', 1)[-1]]
        return set(schema.get('properties', {}))

    def test_106_operations_generees(self):
        operations = {(m.upper(), p.removeprefix(PREFIXE)) for p, item in self.schema['paths'].items()
                      for m in item if m in METHODES_HTTP}
        self.assertEqual(operations, set(ROUTES))

    def test_aucun_avertissement_sur_les_routes_schematisees(self):
        for methode, chemin in self.couverts:
            nom = module_de(chemin)
            fichiers = (f'views/{nom}.py', f'views\\{nom}.py')  # chemin POSIX (CI) ou Windows
            for message in self.messages:
                with self.subTest(chemin=chemin, message=message[:160]):
                    self.assertFalse(any(f in message for f in fichiers))
                    self.assertNotIn(f"'{PREFIXE}{chemin}'", message)

    def test_chaque_operation_a_une_reponse_de_succes(self):
        for methode, chemin in self.couverts:
            with self.subTest(methode=methode, chemin=chemin):
                succes = [c for c in self._operation(methode, chemin)['responses'] if c.startswith('2')]
                self.assertTrue(succes)

    def test_aucun_avertissement_du_tout(self):
        """Les 106 opérations sont schématisées : le générateur ne dit plus RIEN (mode strict)."""
        self.assertEqual(set(MODULES_SCHEMATISES), {module_de(c) for _, c in ROUTES})
        self.assertEqual(self.messages, [])

    def test_chaque_echantillon_est_la_forme_de_sa_route(self):
        verifies = set()
        for fichier in sorted(ECHANTILLONS.glob('*.json')):
            if fichier.stem in ECHANTILLONS_PARTIELS:
                continue
            document = json.loads(fichier.read_text(encoding='utf-8'))
            methode, _, chemin = document['endpoint'].partition(' ')
            couple = (methode, chemin.removeprefix(PREFIXE))
            if couple not in self.couverts:
                continue
            reponses = self._operation(*couple)['responses']
            formes = [self._proprietes(contenu) for code, r in reponses.items() if code.startswith('2')
                      for contenu in r.get('content', {}).values()]
            with self.subTest(echantillon=fichier.stem):
                self.assertIn(set(document['exemple']), formes)
            verifies.add(fichier.stem)
        tous = {f.stem for f in ECHANTILLONS.glob('*.json')} - ECHANTILLONS_PARTIELS
        self.assertEqual(tous - verifies, set(), 'échantillon dont la route est introuvable')


class PermissionSansBaseTests(SimpleTestCase):
    def _compte(self, *, permissions=None, legacy='', superuser=False):
        compte = get_user_model()(pk=1, company_id=1, is_superuser=superuser, role_legacy=legacy)
        if permissions is not None:
            compte.role = Role(pk=1, company_id=1, nom='r', permissions=permissions)
        return compte

    def _autorise(self, compte):
        return PermissionTaches().has_permission(SimpleNamespace(user=compte), None)

    def test_role_fin_avec_le_droit(self):
        self.assertTrue(self._autorise(self._compte(permissions=['taches_voir'])))

    def test_role_fin_sans_le_droit(self):
        self.assertFalse(self._autorise(self._compte(permissions=['crm_voir', 'roles_gerer'])))

    def test_compte_herite_responsable_sans_role_refuse(self):
        compte = self._compte(legacy=get_user_model().ROLE_RESPONSABLE)
        self.assertTrue(compte.is_responsable)
        self.assertFalse(self._autorise(compte))

    def test_superutilisateur(self):
        self.assertTrue(self._autorise(self._compte(superuser=True)))


class AssistantEtBouchonTests(SimpleTestCase):
    def setUp(self):
        self.usine = RequestFactory()

    def test_bearer_sans_entete_est_l_assistant(self):
        self.assertTrue(est_assistant(self.usine.get('/', HTTP_AUTHORIZATION='Bearer abc.def')))

    def test_entete_sans_bearer_est_l_assistant(self):
        self.assertTrue(est_assistant(self.usine.get('/', HTTP_X_TAQINOR_ASSISTANT='1')))

    def test_navigateur_au_cookie_n_est_pas_l_assistant(self):
        requete = self.usine.get('/')
        requete.COOKIES['access_token'] = 'abc.def'
        self.assertFalse(est_assistant(requete))

    def test_bouchon_refuse_tout_en_401(self):
        bouchon = JetonPasEncoreLivre()
        for requete in (self.usine.get('/'), self.usine.get('/', HTTP_AUTHORIZATION='Bearer tqc_x')):
            with self.assertRaises(AuthenticationFailed):
                bouchon.authenticate(requete)
        self.assertTrue(bouchon.authenticate_header(self.usine.get('/')).startswith('Bearer'))

    def test_routes_a_jeton_405_avant_le_bouchon(self):
        """api-fuzz « Unsupported methods » : TRACE/PUT (non servies) → 405 avant le bouchon ;
        la méthode servie reste un 401 neutre."""
        usine = APIRequestFactory()
        for methode, chemin in sorted(ROUTES_A_JETON):
            correspondance = resolve(concret(chemin))
            vue = correspondance.func
            for autre in ('TRACE', 'PUT'):
                with self.subTest(chemin=chemin, methode=autre):
                    reponse = vue(usine.generic(autre, concret(chemin)), **correspondance.kwargs)
                    self.assertEqual(reponse.status_code, 405)
                    self.assertNotIn('WWW-Authenticate', reponse)
            with self.subTest(chemin=chemin, methode=methode):
                reponse = vue(usine.generic(methode, concret(chemin)), **correspondance.kwargs)
                self.assertEqual(reponse.status_code, 401)
                self.assertIn('WWW-Authenticate', reponse)


class EntreesMalFormeesTests(TestCase):
    """Revue F2 tour 2 #12 : une entrée mal formée répond 400 sous son champ, jamais 500, et rien n'est écrit.

    Une table (route, méthode, entrée fabriquée) parcourue en `subTest` ; chaque famille a son cas témoin
    (une entrée VALIDE proche passe toujours). Horloge figée : « aujourd'hui » est le 18/11/2026."""

    HORS_BORNES = ('9999-12-31', '0001-01-01', '2101-01-01', '1999-12-31')
    REGLE = {'frequence': 'hebdo', 'intervalle': 1, 'jours_semaine': '1000000', 'mode': 'calendrier'}

    @classmethod
    def setUpTestData(cls):
        cls.soc = fabriques.societe('a')
        cls.u = fabriques.compte(cls.soc, nom='u1', admin=True)
        fabriques.reglages(cls.u)
        cls.p = fabriques.projet(cls.u, priorite=2)
        cls.t = fabriques.tache(cls.u, projet=cls.p, jour_prevu=datetime.date(2026, 11, 18))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.u)
        self.api.raise_request_exception = False

    def _ecritures(self):
        modeles = apps.get_app_config('taches').get_models()
        return {m.__name__: m._base_manager.count() for m in modeles}

    def _envoyer(self, methode, chemin, entree):
        if methode == 'get':
            return self.api.get(PREFIXE + chemin, entree)
        return getattr(self.api, methode)(PREFIXE + chemin, entree, format='json')

    def _cas_dates(self, jour):
        p, t = self.p.pk, self.t.pk
        return [
            ('get', 'aujourdhui/', {'jour': jour}, 'jour'),
            ('get', 'journee/proposition/', {'jour': jour}, 'jour'),
            ('get', 'agenda/', {'du': jour, 'au': '2026-11-20'}, 'du'),
            ('get', 'agenda/', {'du': '2026-11-18', 'au': jour}, 'au'),
            ('get', 'revue/projets/', {'semaine': jour}, 'semaine'),
            ('put', f'revue/projets/{p}/', {'semaine': jour, 'decision': 'garder'}, 'semaine'),
            ('post', 'journee/planifier/', {'jour': jour, 'mode': 'express', 'lignes': [], 'essentielles': []}, 'jour'),
            ('post', 'journee/alleger/', {'jour': jour, 'garder': [t]}, 'jour'),
            ('post', 'journee/cloturer/', {'jour': '2026-11-17', 'choix': [{'id': t, 'choix': 'jour', 'jour': jour}]},
             None),
            ('post', 'taches/', {'titre': 'a', 'jour_prevu': jour}, 'jour_prevu'),
            ('post', 'taches/', {'titre': 'a', 'echeance': jour}, 'echeance'),
            ('post', 'taches/', {'titre': 'r', 'recurrence': {**self.REGLE, 'date_debut': jour}}, None),
            ('post', 'taches/', {'titre': 'r', 'jour_prevu': '2026-11-20', 'rappel': {'jour': jour, 'heure': '09:00'}},
             None),
            ('post', 'saisie-rapide/', {'lignes': [{'titre': 'r', 'recurrence': {**self.REGLE, 'date_debut': jour}}]},
             None),
            ('post', 'saisie-rapide/', {'lignes': [{'titre': 'a', 'jour_prevu': jour}]}, None),
        ]

    def test_dates_hors_bornes_rendent_400_sans_ecriture(self):
        with frozen('2026-11-18 10:00:00'):
            for jour in self.HORS_BORNES:
                for methode, chemin, entree, champ in self._cas_dates(jour):
                    avant = self._ecritures()
                    with self.subTest(jour=jour, methode=methode, chemin=chemin, entree=entree):
                        reponse = self._envoyer(methode, chemin, entree)
                        self.assertEqual(reponse.status_code, 400, reponse.content[:300])
                        if champ is not None:
                            self.assertIn(champ, reponse.json())
                        self.assertEqual(self._ecritures(), avant)

    def test_temoin_dates_de_2026_passent(self):
        with frozen('2026-11-18 10:00:00'):
            jour = '2026-11-19'
            for methode, chemin, entree, _champ in self._cas_dates(jour):
                with self.subTest(methode=methode, chemin=chemin):
                    reponse = self._envoyer(methode, chemin, entree)
                    self.assertLess(reponse.status_code, 400, reponse.content[:300])


class AccesTests(TestCase):
    """Les 106 routes, par de vraies requêtes : 403 sans le droit, 501 avec, 401 sur les jetons."""

    @classmethod
    def setUpTestData(cls):
        societe = fabriques.societe('a')
        cls.voir = fabriques.compte(societe, nom='voir')
        cls.admin = fabriques.compte(societe, admin=True, nom='admin')
        cls.sans_droit = fabriques.compte(societe, voir=False, nom='sansdroit')
        cls.herite = get_user_model().objects.create_user(
            username=f'herite@{societe.slug}', password=None, company=societe,
            role_legacy=get_user_model().ROLE_RESPONSABLE)

    def _appel(self, client, methode, chemin):
        return getattr(client, methode.lower())(concret(chemin), {}, format='json')

    def _client(self, compte):
        client = APIClient()
        client.force_authenticate(compte)
        return client

    def test_sans_le_droit_403_pour_tout_compte(self):
        for compte in (self.sans_droit, self.herite):
            client = self._client(compte)
            for methode, chemin in ROUTES:
                if (methode, chemin) in ROUTES_A_JETON:
                    continue
                with self.subTest(compte=compte.username, methode=methode, chemin=chemin):
                    self.assertEqual(self._appel(client, methode, chemin).status_code, 403)

    def test_avec_le_droit_501(self):
        client_voir, client_admin = self._client(self.voir), self._client(self.admin)
        for methode, chemin in ROUTES:
            if (methode, chemin) in ROUTES_A_JETON or est_construite(methode, chemin):
                continue
            client = client_admin if (methode, chemin) in ROUTES_ADMIN else client_voir
            with self.subTest(methode=methode, chemin=chemin):
                reponse = self._appel(client, methode, chemin)
                self.assertEqual(reponse.status_code, 501)
                self.assertEqual(reponse.json()['detail'], PasEncore.default_detail)

    def test_coupe_circuit_refuse_hors_administrateur(self):
        client = self._client(self.voir)
        for methode, chemin in ROUTES_ADMIN:
            with self.subTest(methode=methode):
                self.assertEqual(self._appel(client, methode, chemin).status_code, 403)

    def test_anonyme_401(self):
        self.assertEqual(self._appel(APIClient(), 'GET', 'aujourdhui/').status_code, 401)

    def test_routes_a_jeton_401_neutre(self):
        jwt = APIClient()
        jwt.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.voir)}')
        faux = APIClient()
        faux.credentials(HTTP_AUTHORIZATION='Bearer tqc_inconnu')
        for methode, chemin in sorted(ROUTES_A_JETON):
            corps = []
            for client in (APIClient(), jwt, faux):
                reponse = self._appel(client, methode, chemin)
                with self.subTest(methode=methode, chemin=chemin):
                    self.assertEqual(reponse.status_code, 401)
                    self.assertIn('WWW-Authenticate', reponse)
                corps.append(reponse.json()['detail'])
            self.assertEqual(len(set(corps)), 1, 'un refus ne dit jamais pourquoi')

    def test_routes_a_jeton_methode_non_servie_405(self):
        """Par la pile complète (intergiciels compris) : TRACE et PUT → 405, même avec un jeton."""
        faux = APIClient()
        faux.credentials(HTTP_AUTHORIZATION='Bearer tqc_inconnu')
        for _methode, chemin in sorted(ROUTES_A_JETON):
            for client in (APIClient(), faux):
                for autre in ('TRACE', 'PUT'):
                    with self.subTest(chemin=chemin, methode=autre):
                        self.assertEqual(client.generic(autre, concret(chemin)).status_code, 405)
