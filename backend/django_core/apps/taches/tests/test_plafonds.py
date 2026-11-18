"""TCH129 — plafonds de requêtes des routes de F2 (reference/api.md §10 ; `docs/query-budgets.yml`).

Les CIBLES d'api.md §10 (A15, R13) sont les plafonds `assertMaxQueries` ci-dessous ; la CI mesure (un
dépassement donne le compte réel et la liste des requêtes), et la cible devient la mesure au premier
vert (17/11 : badge 11, proposition 25, agenda 35, vue d'un projet 20, recherche 10 ; les listes
restent O(1)). Authentification par le cookie `access_token` : le chemin du navigateur, requêtes
d'authentification comprises, jamais l'en-tête de l'assistant. Chaque route est appelée une fois avant
la mesure (caches du processus chauds : types de contenu, calendrier) : on mesure le régime permanent.
Les listes ne grandissent pas avec leurs lignes (motif 10 → 25 du manifeste) ; l'aperçu de la saisie
rapide est constant en lignes (§10).

Routes de §10 pas encore construites (`journee/priorites/`, `journee/point/`, `suggestions/`) :
déclarées `enforced: false` dans le manifeste, sans test ici. `tuile/` et `flux/` (TCH97) sont mesurées
par LEUR jeton, authentification comprise ; leurs plafonds sont une estimation (≈ badge mesuré + ce que
lit la route de plus) au-dessus des cibles de §10 (10 et 8), à ramener à la mesure au premier vert.
`saisie-rapide/` est un POST : le manifeste ne garde que des routes GET (`check_query_budgets._routes_get`),
son plafond vit ici.
"""
import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import ElementChecklist, Etiquette, EtiquetteTache, Rappel
from apps.taches.tests import fabriques
from core.test_utils import AssertQueryBudgetMixin

URL_AUJOURDHUI = '/api/django/taches/aujourdhui/'
URL_BADGE = '/api/django/taches/badge/'
URL_PROPOSITION = '/api/django/taches/journee/proposition/'
URL_AGENDA = '/api/django/taches/agenda/'
URL_TACHES = '/api/django/taches/taches/'
URL_PROJETS = '/api/django/taches/projets/'
URL_VUE_PROJET = '/api/django/taches/projets/{id}/vue/'
URL_SAISIE = '/api/django/taches/saisie-rapide/'
URL_RYTHME = '/api/django/taches/rythme/'
URL_RECHERCHE = '/api/django/taches/recherche/'
URL_TUILE = '/api/django/taches/tuile/'
URL_FLUX = '/api/django/taches/flux/{jeton}.ics'


def _porteur(clair):
    """Client du jeton `tuile` (en-tête), comme Scriptable ; le flux porte le sien dans l'adresse."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {clair}')
    return api


def _peupler(compte, projets, etiquette, jour, nombre, depart=0):
    """`nombre` tâches du jour, à tour de rôle dans `projets`, chacune avec une étiquette, un point de
    check-list, une sous-tâche et un rappel (les relations que lisent ITEM et TACHE) ; autant de tâches
    sans jour dans les projets (candidates de Proposé) ; une tâche À trier."""
    societe = compte.company
    for rang in range(depart, depart + nombre):
        projet = projets[rang % len(projets)]
        tache = fabriques.tache(compte, projet=projet, jour_prevu=jour, titre=f'Devis {rang}', priorite=rang % 4)
        EtiquetteTache.objects.create(company=societe, tache=tache, etiquette=etiquette)
        ElementChecklist.objects.create(company=societe, tache=tache, libelle='Prix', rang=1024)
        fabriques.tache(compte, projet=projet, parent=tache, titre=f'Relire {rang}')
        Rappel.objects.create(company=societe, proprietaire=compte, tache=tache, jour=jour,
                              heure=datetime.time(18, 0))
        fabriques.tache(compte, projet=projet, titre=f'Préparer {rang}', estimation_minutes=30)
    fabriques.tache(compte, titre=f'À trier {depart}')


class PlafondsTests(AssertQueryBudgetMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        cls.compte = fabriques.compte(fabriques.societe('plafonds'), nom='plafonds')
        fabriques.reglages(cls.compte)
        cls.projets = [fabriques.projet(cls.compte, priorite=priorite) for priorite in (3, 2, 0)]
        fabriques.section(cls.projets[0])
        cls.etiquette = Etiquette.objects.create(company=cls.compte.company, proprietaire=cls.compte, nom='magasin')
        fabriques.activite(cls.compte)
        _peupler(cls.compte, cls.projets, cls.etiquette, cls.jour, 6)

    def setUp(self):
        self.api = APIClient()
        self.api.cookies['access_token'] = str(AccessToken.for_user(self.compte))

    def _lire(self, url):
        reponse = self.api.get(url)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse

    def _erp_dans_journee(self, allume):
        ReglagesRythme.objects.filter(proprietaire=self.compte).update(erp_dans_journee=allume)

    def test_aujourdhui_sans_familles_erp(self):
        self._erp_dans_journee(False)
        self._lire(URL_AUJOURDHUI)
        with self.assertMaxQueries(26):
            self._lire(URL_AUJOURDHUI)

    def test_aujourdhui_avec_familles_erp(self):
        self._erp_dans_journee(True)
        self._lire(URL_AUJOURDHUI)
        with self.assertMaxQueries(31):
            self._lire(URL_AUJOURDHUI)

    def test_badge(self):
        self._lire(URL_BADGE)
        with self.assertMaxQueries(14):  # mesuré 14 depuis que `badge/` porte `a_trier` (PlafondsFigesTests)
            self._lire(URL_BADGE)

    def test_proposition_du_jour(self):
        self._lire(URL_PROPOSITION)
        with self.assertMaxQueries(27):
            self._lire(URL_PROPOSITION)

    def test_agenda(self):
        self._lire(URL_AGENDA)
        with self.assertMaxQueries(28):
            self._lire(URL_AGENDA)

    def _requetes(self, url):
        self._lire(url)
        with CaptureQueriesContext(connection) as capture:
            self._lire(url)
        return len(capture)

    def test_agenda_ne_grandit_ni_avec_les_taches_ni_avec_les_jours(self):
        """Une seule lecture préchargée pour toute la fenêtre : 7 ou 42 jours, 6 ou 12 tâches du jour,
        le même nombre de requêtes."""
        court = f'{URL_AGENDA}?du={self.jour.isoformat()}&au={(self.jour + datetime.timedelta(days=6)).isoformat()}'
        long = f'{URL_AGENDA}?du={self.jour.isoformat()}&au={(self.jour + datetime.timedelta(days=41)).isoformat()}'
        avant_court, avant_long = self._requetes(court), self._requetes(long)
        self.assertEqual(avant_court, avant_long)
        _peupler(self.compte, self.projets, self.etiquette, self.jour + datetime.timedelta(days=2), 6, depart=100)
        self.assertEqual(self._requetes(court), avant_court)
        self.assertEqual(self._requetes(long), avant_long)

    def test_liste_des_taches(self):
        self._lire(URL_TACHES)
        with self.assertMaxQueries(12):
            self._lire(URL_TACHES)

    def test_liste_des_projets(self):
        self._lire(URL_PROJETS)
        with self.assertMaxQueries(14):
            self._lire(URL_PROJETS)

    def test_vue_d_un_projet(self):
        url = URL_VUE_PROJET.format(id=self.projets[0].pk)
        self._lire(url)
        with self.assertMaxQueries(22):
            self._lire(url)

    def test_apercu_de_la_saisie_rapide(self):
        corps = {'texte': 'Appeler le fournisseur demain 10 h\nDevis Settat #Ventes\nAcheter des câbles'}
        self.assertEqual(self.api.post(URL_SAISIE, corps, format='json').status_code, 200)
        with self.assertMaxQueries(11):
            reponse = self.api.post(URL_SAISIE, corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])

    def test_rythme(self):
        self._lire(URL_RYTHME)
        with self.assertMaxQueries(10):
            self._lire(URL_RYTHME)

    def test_recherche(self):
        url = f'{URL_RECHERCHE}?q=Devis'
        self._lire(url)
        with self.assertMaxQueries(12):
            self._lire(url)

    def test_tuile(self):
        """TCH97 — jeton `tuile` (authentification comprise) ; cible d'api.md §10 : 10."""
        porteur = _porteur(fabriques.jeton(self.compte, 'tuile')[1])
        self.assertEqual(porteur.get(URL_TUILE).status_code, 200)
        with self.assertMaxQueries(14):
            self.assertEqual(porteur.get(URL_TUILE).status_code, 200)

    def test_flux(self):
        """TCH97 — jeton `flux` dans l'adresse (authentification comprise) ; cible d'api.md §10 : 8."""
        url = URL_FLUX.format(jeton=fabriques.jeton(self.compte, 'flux')[1])
        self.assertEqual(APIClient().get(url).status_code, 200)
        with self.assertMaxQueries(10):
            self.assertEqual(APIClient().get(url).status_code, 200)


class PlafondsConstantsTests(TestCase):
    """Le nombre de requêtes ne grandit pas avec les lignes (O(1)) : listes et aperçu de la saisie."""

    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        cls.compte = fabriques.compte(fabriques.societe('plafonds-o1'), nom='plafonds')
        fabriques.reglages(cls.compte)
        cls.projets = [fabriques.projet(cls.compte, priorite=priorite) for priorite in (3, 2)]
        cls.etiquette = Etiquette.objects.create(company=cls.compte.company, proprietaire=cls.compte, nom='magasin')
        _peupler(cls.compte, cls.projets, cls.etiquette, cls.jour, 4)

    def setUp(self):
        self.api = APIClient()
        self.api.cookies['access_token'] = str(AccessToken.for_user(self.compte))

    def _compter(self, appel):
        """Le nombre de requêtes d'`appel()` en régime permanent (un appel de chauffe d'abord)."""
        self.assertEqual(appel().status_code, 200)
        with CaptureQueriesContext(connection) as requetes:
            reponse = appel()
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return len(requetes.captured_queries)

    def test_la_liste_des_taches_ne_grandit_pas(self):
        avant = self._compter(lambda: self.api.get(URL_TACHES))
        _peupler(self.compte, self.projets, self.etiquette, self.jour, 8, depart=100)
        self.assertEqual(self._compter(lambda: self.api.get(URL_TACHES)), avant)

    def test_la_liste_des_projets_ne_grandit_pas(self):
        avant = self._compter(lambda: self.api.get(URL_PROJETS))
        for priorite in (1, 0, 3, 2, 1):
            projet = fabriques.projet(self.compte, priorite=priorite)
            _peupler(self.compte, [projet], self.etiquette, self.jour, 1, depart=200 + priorite)
        self.assertEqual(self._compter(lambda: self.api.get(URL_PROJETS)), avant)

    def test_la_tuile_et_le_flux_ne_grandissent_pas_avec_les_taches(self):
        """TCH97 — une lecture préchargée : 4 ou 12 tâches du jour (et de J + 3), même compte."""
        tuile = _porteur(fabriques.jeton(self.compte, 'tuile')[1])
        flux = URL_FLUX.format(jeton=fabriques.jeton(self.compte, 'flux')[1])
        avant_tuile = self._compter(lambda: tuile.get(URL_TUILE))
        avant_flux = self._compter(lambda: APIClient().get(flux))
        _peupler(self.compte, self.projets, self.etiquette, self.jour, 8, depart=300)
        _peupler(self.compte, self.projets, self.etiquette, self.jour + datetime.timedelta(days=3), 4, depart=400)
        self.assertEqual(self._compter(lambda: tuile.get(URL_TUILE)), avant_tuile)
        self.assertEqual(self._compter(lambda: APIClient().get(flux)), avant_flux)

    def test_l_apercu_de_la_saisie_est_constant_en_lignes(self):
        def apercu(lignes):
            texte = '\n'.join(f'Appeler le client {rang} demain' for rang in range(lignes))
            return lambda: self.api.post(URL_SAISIE, {'texte': texte}, format='json')
        self.assertEqual(self._compter(apercu(12)), self._compter(apercu(3)))

    def test_la_proposition_du_jour_ne_grandit_pas(self):
        """Plafond 27 : 4 puis 16 tâches du jour (et autant de candidates sans jour), le même nombre de requêtes."""
        avant = self._compter(lambda: self.api.get(URL_PROPOSITION))
        _peupler(self.compte, self.projets, self.etiquette, self.jour, 12, depart=300)
        self.assertEqual(self._compter(lambda: self.api.get(URL_PROPOSITION)), avant)

    def test_la_vue_d_un_projet_ne_grandit_pas(self):
        """Plafond 22 : 4 puis 16 tâches du jour dans le projet, le même nombre de requêtes."""
        url = URL_VUE_PROJET.format(id=self.projets[0].pk)
        avant = self._compter(lambda: self.api.get(url))
        _peupler(self.compte, self.projets[:1], self.etiquette, self.jour, 12, depart=400)
        self.assertEqual(self._compter(lambda: self.api.get(url)), avant)


# ── F3 · Copilote et iPhone : plafonds à HORLOGE FIGÉE, posés à la mesure ─────────────────────────────
# Un mardi ordinaire (le Maroc est à UTC+0). Avant midi, la journée lit en plus le plan de la veille et
# ses restes (`services/journee._carte_bilan_hier`) : toute route qui passe par la journée est mesurée
# AUX DEUX MOMENTS, chacun avec son plafond (mesurés le 18/11/2026 sur la base de la lane).
JOUR_FIGE = datetime.date(2026, 11, 24)
MATIN, APRES_MIDI = '2026-11-24 09:00:00', '2026-11-24 15:00:00'
URL_PRIORITES = '/api/django/taches/journee/priorites/'
URL_POINT = '/api/django/taches/journee/point/'
#: route : (plafond à 09:00, plafond à 15:00).
PLAFONDS_FIGES = {
    URL_PRIORITES: (21, 21),   # TCH161 « Aide-moi à prioriser » ; cible api.md §10 : 20
    URL_POINT: (26, 24),       # TCH161 « Où j'en suis ? » ; cible api.md §10 : 18
    URL_BADGE: (14, 14),       # la pastille (porte `a_trier`)
    URL_TUILE: (14, 14),       # TCH97, jeton tuile, authentification comprise ; cible 10
    URL_FLUX: (9, 9),          # TCH97, jeton flux dans l'adresse, authentification comprise ; cible 8
}


def _fige(moment):
    """L'horloge figée de la maison (freezegun)."""
    from testkit.time import frozen
    return frozen(moment)


class PlafondsFigesTests(AssertQueryBudgetMixin, TestCase):
    """Copilote (`journee/priorites/`, `journee/point/`), pastille, tuile et flux : régime permanent (un
    appel de chauffe d'abord), horloge figée à 09:00 puis 15:00 ; les deux routes du Copilote ne
    grandissent pas avec les tâches."""

    @classmethod
    def setUpTestData(cls):
        with _fige(APRES_MIDI):
            cls.compte = fabriques.compte(fabriques.societe('plafonds-figes'), nom='plafonds')
            fabriques.reglages(cls.compte)
            cls.projets = [fabriques.projet(cls.compte, priorite=priorite) for priorite in (3, 2, 0)]
            fabriques.section(cls.projets[0])
            cls.etiquette = Etiquette.objects.create(company=cls.compte.company, proprietaire=cls.compte,
                                                     nom='magasin')
            fabriques.activite(cls.compte)
            _peupler(cls.compte, cls.projets, cls.etiquette, JOUR_FIGE, 6)
            cls.jeton_tuile = fabriques.jeton(cls.compte, 'tuile')[1]
            cls.jeton_flux = fabriques.jeton(cls.compte, 'flux')[1]

    def _appel(self, url):
        if url == URL_TUILE:
            return lambda: _porteur(self.jeton_tuile).get(URL_TUILE)
        if url == URL_FLUX:
            return lambda: APIClient().get(URL_FLUX.format(jeton=self.jeton_flux))
        api = APIClient()
        api.cookies['access_token'] = str(AccessToken.for_user(self.compte))
        return lambda: api.get(url)

    def _compter(self, url):
        appel = self._appel(url)
        self.assertEqual(appel().status_code, 200)
        with CaptureQueriesContext(connection) as capture:
            reponse = appel()
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return len(capture)

    def test_plafonds_aux_deux_moments(self):
        for url, plafonds in PLAFONDS_FIGES.items():
            for moment, plafond in zip((MATIN, APRES_MIDI), plafonds):
                with self.subTest(url=url, moment=moment), _fige(moment):
                    appel = self._appel(url)
                    self.assertEqual(appel().status_code, 200)
                    with self.assertMaxQueries(plafond):
                        self.assertEqual(appel().status_code, 200)

    def test_le_manifeste_porte_le_plus_haut_plafond_mesure(self):
        """`docs/query-budgets.yml` garde chaque route au plus haut de ses deux plafonds mesurés."""
        import yaml
        from pathlib import Path
        manifeste = Path(__file__).resolve().parents[5] / 'docs' / 'query-budgets.yml'
        budgets = {e['path']: e for e in yaml.safe_load(manifeste.read_text(encoding='utf-8'))['endpoints']}
        for url, plafonds in PLAFONDS_FIGES.items():
            with self.subTest(url=url):
                self.assertEqual((budgets[url]['budget'], budgets[url]['enforced']), (max(plafonds), True))

    def test_priorites_et_point_ne_grandissent_pas(self):
        """6 puis 18 tâches du jour (et autant de candidates sans jour) : le même nombre, à chaque moment."""
        avant = {}
        for moment in (MATIN, APRES_MIDI):
            with _fige(moment):
                avant[moment] = [self._compter(URL_PRIORITES), self._compter(URL_POINT)]
        with _fige(APRES_MIDI):
            _peupler(self.compte, self.projets, self.etiquette, JOUR_FIGE, 12, depart=500)
        for moment in (MATIN, APRES_MIDI):
            with self.subTest(moment=moment), _fige(moment):
                self.assertEqual([self._compter(URL_PRIORITES), self._compter(URL_POINT)], avant[moment])
