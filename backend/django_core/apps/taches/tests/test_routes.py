"""TCH15 — toutes les routes de l'app `taches` déclarées, gardées, et pas encore construites.

Sans base (SimpleTestCase) : les 106 couples méthode × chemin de reference/api.md §3 résolvent,
chaque chemin sert EXACTEMENT ses méthodes, chaque vue lève `PasEncore` (501) et porte la
permission STRICTE ; `est_assistant`, la permission et l'authentification des routes à jeton (chacune
celle de SON usage, TCH95).
Avec base (TestCase, CI) : 403 sans `taches_voir` pour tout compte (y compris un compte hérité
« responsable » sans rôle fin), 501 avec, refus neutre sur capture et tuile (401), flux (404).
"""
import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.taches.auth_jeton import JetonAccesAuthentication, JetonCapture, JetonFlux, JetonTuile
from apps.taches.tests import fabriques
from apps.taches.views.base import PasEncore, PermissionTaches, est_assistant

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
#: Routes à jeton (J:x) → l'authentification de LEUR usage (et elle seule).
AUTH_PAR_ROUTE = {('POST', 'capture/'): JetonCapture, ('GET', 'tuile/'): JetonTuile,
                  ('GET', 'flux/{jeton}.ics'): JetonFlux}
ROUTES_A_JETON = set(AUTH_PAR_ROUTE)
#: Statut du refus neutre : 404 pour le flux (le jeton est dans l'adresse), 401 sinon.
STATUT_REFUS = {('GET', 'flux/{jeton}.ics'): 404}
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
                a_jeton = [a for a in vue.authentication_classes if issubclass(a, JetonAccesAuthentication)]
                attendue = AUTH_PAR_ROUTE.get((methode, chemin))
                if attendue is None:
                    self.assertEqual(a_jeton, [])
                else:
                    self.assertEqual(list(vue.authentication_classes), [attendue])

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
#: carte de fichier (gabarits des liens) ; `ecriture_a_valider` = `donnees` d'une carte posée par le
#: relais du Copilote (A5).
ECHANTILLONS_PARTIELS = {'item', 'carte_du_moment', 'rendez_vous', 'proposition', 'erreurs', 'liens_cibles',
                         'ecriture_a_valider'}
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

    def test_jeton_absent_ou_mal_forme_refuse_sans_lire_la_base(self):
        """Sans base : aucun en-tête, un autre schéma, un préfixe d'un autre usage ou un clair trop
        court sont refusés AVANT toute requête (le refus neutre ne dépend que de la forme)."""
        for classe in (JetonCapture, JetonTuile):
            for entete in ('', 'Basic abc', 'Bearer tqf_' + 'a' * 43, 'Bearer tqc_x', 'Bearer'):
                with self.subTest(classe=classe.__name__, entete=entete[:12]):
                    requete = self.usine.get('/', HTTP_AUTHORIZATION=entete) if entete else self.usine.get('/')
                    with self.assertRaises(AuthenticationFailed):
                        classe().authenticate(requete)
            self.assertTrue(classe().authenticate_header(self.usine.get('/')).startswith('Bearer'))
        flux = JetonFlux()
        for clair in ('', 'tqc_' + 'a' * 43, 'tqf_court'):
            requete = SimpleNamespace(parser_context={'kwargs': {'jeton': clair}})
            with self.subTest(clair=clair[:6]), self.assertRaises(NotFound):
                flux.authenticate(requete)

    def test_routes_a_jeton_405_avant_le_jeton(self):
        """api-fuzz « Unsupported methods » : TRACE/PUT (non servies) → 405 avant l'authentification ;
        la méthode servie reste un refus neutre (401, 404 pour le flux)."""
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
                refus = STATUT_REFUS.get((methode, chemin), 401)
                self.assertEqual(reponse.status_code, refus)
                self.assertEqual('WWW-Authenticate' in reponse, refus == 401)


class AccesTests(TestCase):
    """Les 106 routes, par de vraies requêtes : 403 sans le droit, 501 avec, refus neutre sur les jetons."""

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
            refus = STATUT_REFUS.get((methode, chemin), 401)
            for client in (APIClient(), jwt, faux):
                reponse = self._appel(client, methode, chemin)
                with self.subTest(methode=methode, chemin=chemin):
                    self.assertEqual(reponse.status_code, refus)
                    self.assertEqual('WWW-Authenticate' in reponse, refus == 401)
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


class BearerSansEnteteTests(TestCase):
    """TCH163 — invariant 37 (api.md §0, R22) : un appel en `Authorization: Bearer` SANS l'en-tête
    `X-Taqinor-Assistant` est servi en mode ASSISTANT (titre confidentiel masqué, notes absentes) —
    l'oubli de l'en-tête par le relais échoue FERMÉ ; le navigateur (cookie) voit tout."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('bearer'))
        secret = fabriques.projet(cls.compte, nom='Canari-projet', confidentiel=True)
        cls.tache = fabriques.tache(cls.compte, projet=secret, titre='Canari-titre', notes='Canari-notes')

    def _lire(self, client):
        reponse = client.get(f'/api/django/taches/taches/{self.tache.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse

    def test_bearer_seul_masque_titre_et_notes(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.compte)}')
        reponse = self._lire(client)
        self.assertNotIn('canari', reponse.content.decode('utf-8').lower())
        self.assertEqual(reponse.json()['notes'], '')

    def test_le_navigateur_au_cookie_voit_tout(self):
        client = APIClient()
        client.cookies['access_token'] = str(AccessToken.for_user(self.compte))
        rendu = self._lire(client).json()
        self.assertEqual((rendu['titre'], rendu['notes']), ('Canari-titre', 'Canari-notes'))


class FermeesALAssistantTests(TestCase):
    """api.md §0 — en mode assistant (en-tête OU `Authorization: Bearer`), 403 sur `reglages/`,
    `reglages-societe/`, `jetons/`, `mes-donnees/`, `tout-effacer/` et `agendas-externes/` : le relais du
    Copilote ne lit ni ne change un réglage, un jeton ou un agenda, ne lit pas l'export et n'efface jamais
    rien. Le navigateur (cookie) passe : le refus ne vient pas d'un droit manquant."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('ferme'), admin=True)
        cls.agenda = fabriques.agenda_externe(cls.compte)
        cls.jeton, _clair = fabriques.jeton(cls.compte, 'flux')
        cls.tache = fabriques.tache(cls.compte, titre='À garder')

    def _appels(self):
        agenda, jeton = self.agenda.pk, self.jeton.pk
        return (
            ('get', 'reglages/', None), ('patch', 'reglages/', {}),
            ('get', 'reglages-societe/', None), ('patch', 'reglages-societe/', {'balayage_actif': False}),
            ('get', 'jetons/', None), ('post', 'jetons/', {'usage': 'tuile'}),
            ('post', f'jetons/{jeton}/revoquer/', None),
            ('get', 'mes-donnees/', None),
            ('post', 'tout-effacer/', {'confirmation': 'EFFACER'}),
            ('get', 'agendas-externes/', None),
            ('post', 'agendas-externes/', {'url': 'https://agenda.example/b.ics'}),
            ('patch', f'agendas-externes/{agenda}/', {'libelle': 'Autre'}),
            ('delete', f'agendas-externes/{agenda}/', None),
            ('post', f'agendas-externes/{agenda}/rafraichir/', None),
        )

    def _relais(self):
        entete = APIClient(HTTP_X_TAQINOR_ASSISTANT='1')
        entete.force_authenticate(self.compte)
        bearer = APIClient()
        bearer.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.compte)}')
        return (('en-tête', entete), ('bearer', bearer))

    def test_403_sous_l_assistant_et_rien_n_est_ecrit(self):
        for nom, client in self._relais():
            for methode, chemin, corps in self._appels():
                with self.subTest(relais=nom, route=f'{methode} {chemin}'):
                    reponse = getattr(client, methode)(PREFIXE + chemin, corps, format='json')
                    self.assertEqual(reponse.status_code, 403, reponse.content[:200])
        self.tache.refresh_from_db()
        self.agenda.refresh_from_db()
        self.jeton.refresh_from_db()
        self.assertEqual(self.agenda.libelle, '')
        self.assertIsNone(self.jeton.revoque_le)
        self.assertEqual(self.agenda.__class__.objects.count(), 1)
        self.assertEqual(self.jeton.__class__.objects.count(), 1)

    def test_le_navigateur_au_cookie_passe(self):
        client = APIClient()
        client.cookies['access_token'] = str(AccessToken.for_user(self.compte))
        for chemin in ('reglages/', 'reglages-societe/', 'jetons/', 'mes-donnees/', 'agendas-externes/'):
            with self.subTest(route=chemin):
                self.assertEqual(client.get(PREFIXE + chemin).status_code, 200)
