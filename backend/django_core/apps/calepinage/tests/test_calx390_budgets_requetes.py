"""CALX390 — les budgets de requêtes SQL du module calepinage.

``docs/query-budgets.yml`` est le contrat de perf par endpoint, rendu
opposable par ``scripts/check_query_budgets.py`` (un endpoint
``enforced: true`` sans test de budget qui référence son URL fait rougir le
job ``stage-names``). Ce fichier est CE test pour les trois endpoints du
module :

* ``/api/django/calepinage/calepinages/`` — la liste (``layout_stale`` /
  ``layout_nb_panneaux`` lus, ligne par ligne, sur le devis lié et ses
  lignes) ;
* ``/api/django/calepinage/calepinages/<pk>/`` — le détail agrégé (lead,
  client, devis, compteurs de versions et de variantes, contexte
  géographique, droits) ;
* ``/api/django/calepinage/calepinages/<pk>/resultat/`` — le résultat servi
  (pose, électrique, simulation persistée, fraîcheur).

Patron de la maison (``apps/crm/tests_yopsb13_lead_query_budget.py``) : le
compte est mesuré à 10 puis à 25 objets et ne doit PAS bouger (O(1), pas
O(n)), puis borné par le plafond ÉCRIT dans le manifeste — lu ICI dans
``docs/query-budgets.yml``, jamais recopié, pour que le test et le contrat ne
puissent pas diverger. Un témoin prouve que la garde MORD : sans le
``prefetch_related('devis__lignes')`` du chemin de la liste, le compte grandit
avec les lignes. (Sans le seul ``select_related('devis')``, ce même prefetch
charge les devis en UNE requête : le compte ne grandit pas, il prend une
requête de plus — c'est le plafond qui le voit.)

Le compte est pris en régime PERMANENT : une première requête « à blanc »
chauffe les caches de processus (types de contenu, réglages), comme le fait
YOPSB13 — sans elle, le premier appel porterait une requête unique que le
second n'a plus, et simulerait une croissance.

Run :
    python manage.py test apps.calepinage.tests.test_calx390_budgets_requetes -v2
"""
import pathlib
import re
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.variantes import creer_variante
from apps.calepinage.views.calepinages import CalepinageViewSet
from apps.ventes.models import Devis, LigneDevis
from core.test_utils import AssertQueryBudgetMixin

from .test_api_liste import BaseApiCalepinage

#: Les trois chemins, ÉCRITS tels que le manifeste les déclare (la garde
#: ``check_query_budgets.py`` cherche ces chaînes dans ce fichier).
LISTE = '/api/django/calepinage/calepinages/'
DETAIL = '/api/django/calepinage/calepinages/<pk>/'
#: Lot 4 — la file « à traiter » (8 calepinages de 8 leads à conception rangée), mesurée :
#: 152, puis 122 quand la simulation est LUE sur le stocké (lane I4, résultat servi jamais calculé).
BUDGET_FILE_A_TRAITER = 122
RESULTAT = '/api/django/calepinage/calepinages/<pk>/resultat/'

#: Un document de pose minimal (schéma v2) : deux pans posés.
LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
        {'id': 'b', 'label': 'PAN-B',
         'geometry': {'count': 7, 'azimuthDeg': 90.0, 'tiltDeg': 15.0}},
    ],
}


def _manifeste():
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'query-budgets.yml'
        if candidat.exists():
            return candidat.read_text(encoding='utf-8')
    raise AssertionError('docs/query-budgets.yml introuvable — le contrat de '
                         'perf par endpoint.')


def budget_du_manifeste(chemin):
    """Le plafond ÉCRIT dans le manifeste pour ``chemin`` — et ``enforced``."""
    motif = re.compile(
        r'-\s+path:\s*' + re.escape(chemin) + r'\s*\n'
        r'\s+budget:\s*(\d+)\s*\n'
        r'\s+enforced:\s*(true|false)')
    trouve = motif.search(_manifeste())
    if trouve is None:
        raise AssertionError('Aucune entrée « %s » dans docs/query-budgets.yml '
                             '(path, budget, enforced — dans cet ordre).'
                             % chemin)
    return int(trouve.group(1)), trouve.group(2) == 'true'


def _url(modele, pk):
    return modele.replace('<pk>', str(pk))


#: Lane I4 — les huit dossiers de la file « simulée » : frais (simulation qui décrit encore le
#: document), périmé (empreinte stockée d'un autre document), jamais simulé, et un toit de 60
#: modules sur un onduleur de 10 kW.
CAS_FILE_SIMULEE = ('frais', 'perime', 'jamais', 'grand', 'frais', 'sans_resultat', 'perime', 'frais')


def semer_file_simulee(test, devis):
    """Lane I4 — huit calepinages de huit leads, chacun avec un document posé, une entrée
    électrique et (sauf « jamais » / « sans_resultat ») la simulation déposée par les VRAIS
    écrivains (``calepinage_simule_reel``). Matériel et réglages : les seams des livrables,
    posés pour toute la durée de l'essai ; températures : le TMY rejoué (aucun appel PVGIS)."""
    import copy

    from apps.calepinage.selectors import resultat_servi
    from apps.calepinage.services.electrique import CLE_SIMULATION, enregistrer_fournisseur_temperatures
    from apps.crm.models import Lead

    from .acal_livrables_helpers import LAYOUT_SIMULABLE, calepinage_simule_reel, patch_materiel
    from .test_acal_empreinte_simulation import _tmy_rejoue

    test.addCleanup(enregistrer_fournisseur_temperatures, enregistrer_fournisseur_temperatures(_tmy_rejoue))
    seams = patch_materiel()
    seams.start()
    test.addCleanup(seams.stop)
    simule = calepinage_simule_reel()
    grand = copy.deepcopy(LAYOUT_SIMULABLE)
    grand['zones'][0]['geometry']['count'] = 60
    calepinages = []
    for rang, cas in enumerate(CAS_FILE_SIMULEE):
        resultat = {'sans_resultat': {}, 'jamais': {'entree_electrique': simule.resultat['entree_electrique']}}.get(
            cas, copy.deepcopy(simule.resultat))
        if cas == 'perime':
            resultat[CLE_SIMULATION]['hash_entree'] = 'e' * 64
        lead = Lead.objects.create(company=test.company, nom='Simulée %d' % rang)
        calepinage = Calepinage.objects.create(
            company=test.company, lead_id=lead.pk, devis=devis(), titre='Simulée %d' % rang,
            roof_layout=copy.deepcopy(grand if cas == 'grand' else LAYOUT_SIMULABLE), resultat=resultat)
        if cas in ('frais', 'grand'):  # la simulation décrit ENCORE ce document
            resultat[CLE_SIMULATION]['hash_entree'] = resultat_servi(calepinage)['hash_entree']
            Calepinage.objects.filter(pk=calepinage.pk).update(resultat=resultat)
        calepinages.append(calepinage)
    return calepinages


class BudgetsRequetesCalepinageEnBaseTest(
        AssertQueryBudgetMixin, BaseApiCalepinage):
    """Les trois endpoints : O(1) en lignes, et sous le plafond du manifeste."""

    def setUp(self):
        super().setUp()
        from django.contrib.contenttypes.models import ContentType

        # Caches de processus chauffés AVANT toute mesure (voir l'en-tête).
        ContentType.objects.get_for_model(Calepinage)
        self._rang = 0

    # ── Fabrique ───────────────────────────────────────────────────────────
    def _devis(self):
        """Un devis de la société AVEC une ligne panneau : la péremption la
        lit, c'est donc elle qui doit être chargée d'avance par la liste."""
        self._rang += 1
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='CALX390-%04d' % self._rang, roof_layout=LAYOUT)
        LigneDevis.objects.create(
            devis=devis, designation='Panneau photovoltaïque 710 Wc',
            quantite=Decimal('19'), prix_unitaire=Decimal('1000'))
        return devis

    def _semer_liste(self, nombre):
        for _ in range(nombre):
            Calepinage.objects.create(
                company=self.company, lead_id=self.lead.pk,
                devis=self._devis(), titre='Toiture %d' % self._rang,
                roof_layout=LAYOUT, layout_hash='a' * 64)

    def _pivot(self):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, client=self.client_a,
            devis=self._devis(), titre='Pivot', roof_layout=LAYOUT,
            layout_hash='b' * 64)

    def _semer_lignes_du_pivot(self, pivot, nombre):
        """Les lignes LIÉES qu'un détail agrège : versions et variantes."""
        for _ in range(nombre):
            self._rang += 1
            CalepinageVersion.objects.create(
                company=self.company, calepinage=pivot,
                libelle='Version %d' % self._rang, roof_layout=LAYOUT,
                layout_hash='c' * 64)
            creer_variante(pivot, nom='Variante %d' % self._rang,
                           roof_layout=LAYOUT, resultat={'kwc': 8.6})

    def _compte(self, url):
        with CaptureQueriesContext(connection) as capture:
            reponse = self.api.get(url)
        self.assertEqual(reponse.status_code, 200, getattr(reponse, 'data',
                                                           None))
        return len(capture.captured_queries), reponse

    def _nombre_de_lignes(self, reponse):
        donnees = reponse.data
        return len(donnees['results'] if isinstance(donnees, dict)
                   and 'results' in donnees else donnees)

    # ── La liste ───────────────────────────────────────────────────────────
    def _croissance_liste(self):
        self._compte(LISTE)  # à blanc : régime permanent
        self._semer_liste(10)
        a_10, reponse = self._compte(LISTE)
        self.assertEqual(self._nombre_de_lignes(reponse), 10)
        self._semer_liste(15)
        a_25, reponse = self._compte(LISTE)
        self.assertEqual(self._nombre_de_lignes(reponse), 25)
        return a_10, a_25

    def test_la_liste_ne_grandit_pas_avec_les_lignes(self):
        a_10, a_25 = self._croissance_liste()
        self.assertEqual(
            a_10, a_25,
            'GET %s : %d requêtes à 10 lignes, %d à 25 — N+1. Vérifier le '
            "select_related('client', 'devis') du viewset et le "
            "prefetch_related('devis__lignes') de sa liste." % (
                LISTE, a_10, a_25))
        budget, gardee = budget_du_manifeste(LISTE)
        self.assertTrue(gardee)
        self.assertLessEqual(
            a_25, budget,
            'GET %s : %d requêtes mesurées, plafond %d dans '
            'docs/query-budgets.yml.' % (LISTE, a_25, budget))

    def test_la_liste_tient_son_plafond(self):
        budget, _gardee = budget_du_manifeste(LISTE)
        self._compte(LISTE)
        self._semer_liste(10)
        with self.assertMaxQueries(budget):
            reponse = self.api.get(LISTE)
        self.assertEqual(reponse.status_code, 200)

    def test_la_garde_mord_sans_le_prefetch_des_lignes(self):
        """Témoin : sans ``prefetch_related('devis__lignes')``, ça grandit."""
        def sans_prefetch(vue, queryset):
            return super(CalepinageViewSet, vue).filter_queryset(queryset)

        with mock.patch.object(CalepinageViewSet, 'filter_queryset',
                               sans_prefetch):
            a_10, a_25 = self._croissance_liste()
        self.assertGreater(a_25, a_10)

    # ── Le détail agrégé et le résultat servi ──────────────────────────────
    def _croissance_du_pivot(self, modele):
        pivot = self._pivot()
        url = _url(modele, pivot.pk)
        self._compte(url)  # à blanc : régime permanent
        self._semer_lignes_du_pivot(pivot, 10)
        a_10, _reponse = self._compte(url)
        self._semer_lignes_du_pivot(pivot, 15)
        a_25, reponse = self._compte(url)
        return a_10, a_25, reponse

    def test_le_detail_ne_grandit_pas_avec_versions_et_variantes(self):
        a_10, a_25, reponse = self._croissance_du_pivot(DETAIL)
        self.assertEqual(reponse.data['variantes']['total'], 25)
        self.assertEqual(reponse.data['versions']['total'], 25)
        self.assertEqual(
            a_10, a_25,
            'GET %s : %d requêtes à 10 versions/variantes, %d à 25 — N+1.'
            % (DETAIL, a_10, a_25))
        budget, gardee = budget_du_manifeste(DETAIL)
        self.assertTrue(gardee)
        self.assertLessEqual(
            a_25, budget,
            'GET %s : %d requêtes mesurées, plafond %d dans '
            'docs/query-budgets.yml.' % (DETAIL, a_25, budget))

    def test_le_resultat_ne_grandit_pas_avec_versions_et_variantes(self):
        a_10, a_25, _reponse = self._croissance_du_pivot(RESULTAT)
        self.assertEqual(
            a_10, a_25,
            'GET %s : %d requêtes à 10 versions/variantes, %d à 25 — N+1.'
            % (RESULTAT, a_10, a_25))
        budget, gardee = budget_du_manifeste(RESULTAT)
        self.assertTrue(gardee)
        self.assertLessEqual(
            a_25, budget,
            'GET %s : %d requêtes mesurées, plafond %d dans '
            'docs/query-budgets.yml.' % (RESULTAT, a_25, budget))

    def test_le_resultat_avec_une_conception_rangee_lue_une_fois(self):
        """Relecture E5 (coût des requêtes) — ``resultat/`` d'un lead qui porte une
        conception RANGÉE et un devis ENVOYÉ (bloc ``conception``, filet de péremption,
        écart du devis) : la conception courante n'est lue qu'UNE fois par requête et
        ne coûte que ses lectures propres (9 : version, filet ADEV140 = lead, catalogue,
        deux réglages ; module de la conception ; écart = devis, versions…). Mesuré le
        25/11 : 30 → 22 requêtes, contre 13 sans conception — au-delà du plafond du
        manifeste (15, mesuré sans conception) : décision laissée à l'orchestrateur
        (rapport de la lane E5-fix), budget NON relevé."""
        from django.core.cache import cache

        from apps.ventes import tasks
        from apps.ventes.selectors_conception import conception_courante as vraie

        from .test_acal_cible_lead import ranger_conception

        cache.clear()
        self.addCleanup(cache.clear)
        pivot = self._pivot()
        Devis.objects.filter(pk=pivot.devis_id).update(statut=Devis.Statut.ENVOYE)
        url = _url(RESULTAT, pivot.pk)
        with mock.patch.object(tasks.task_relancer_conception, 'apply_async'):  # jamais le courtier
            self._compte(url)  # à blanc
            sans, _reponse = self._compte(url)
            ranger_conception(lead=self.lead, nb=19, watt=710)
            self._compte(url)
            with mock.patch('apps.ventes.selectors_conception.conception_courante', wraps=vraie) as lue:
                avec, reponse = self._compte(url)
        self.assertEqual(reponse.data['conception']['production_annuelle_kwh'], round(19 * 710 * 1.6, 1))
        self.assertEqual(lue.call_count, 1)  # mutant « sans mémo de requête » : plusieurs lectures
        self.assertLessEqual(avec - sans, 9, 'GET %s : %d requêtes avec une conception rangée, %d sans.'
                             % (RESULTAT, avec, sans))

    def test_detail_et_resultat_tiennent_leur_plafond(self):
        pivot = self._pivot()
        self._semer_lignes_du_pivot(pivot, 10)
        for modele in (DETAIL, RESULTAT):
            with self.subTest(endpoint=modele):
                url = _url(modele, pivot.pk)
                self._compte(url)  # à blanc
                budget, _gardee = budget_du_manifeste(modele)
                with self.assertMaxQueries(budget):
                    reponse = self.api.get(url)
                self.assertEqual(reponse.status_code, 200)

    def test_la_file_a_traiter_ne_calcule_rien_du_moteur(self):
        """Lot 4 (CI rouge du 25/11, api-fuzz : « Read timed out » sur ``a-traiter/?limite=19``) —
        LISTER ne calcule rien du moteur : ni empreinte des entrées (péremption ADEV140), ni
        relance en file, ni repli sur le devis reçu du lead. Mesuré avant le correctif, 8
        calepinages de 8 leads à conception rangée : 203 requêtes et 5 relances en file."""
        from django.core.cache import cache

        from apps.crm.models import Lead
        from apps.ventes import selectors_conception, tasks

        from .test_acal_cible_lead import ranger_conception

        cache.clear()
        self.addCleanup(cache.clear)
        for rang in range(8):
            lead = Lead.objects.create(company=self.company, nom='File %d' % rang)
            ranger_conception(lead=lead, nb=19, watt=710)
            Calepinage.objects.create(company=self.company, lead_id=lead.pk, devis=self._devis(),
                                      titre='File %d' % rang, roof_layout=LAYOUT, layout_hash='d' * 64)
        url = '/api/django/calepinage/calepinages/a-traiter/?limite=19'
        with mock.patch.object(tasks.task_relancer_conception, 'apply_async') as file, \
                mock.patch.object(selectors_conception, '_empreinte_des_entrees',
                                  wraps=selectors_conception._empreinte_des_entrees) as empreinte:
            self._compte(url)  # à blanc
            requetes, _reponse = self._compte(url)
        self.assertEqual((file.call_count, empreinte.call_count), (0, 0))  # mutant « péremption lue » : rouge
        self.assertLessEqual(requetes, BUDGET_FILE_A_TRAITER, 'GET a-traiter/ : %d requêtes' % requetes)

    def test_la_file_a_traiter_ne_sert_pas_le_resultat_entier(self):
        """Lane I4 — la file LIT la simulation stockée (empreinte déposée contre celle
        d'aujourd'hui, P50 stocké) : le résultat servi entier n'est jamais calculé."""
        from apps.calepinage.services import simulation

        semer_file_simulee(self, self._devis)
        interdit = AssertionError('la file a calculé le résultat servi entier')
        url = '/api/django/calepinage/calepinages/a-traiter/?limite=19'
        with mock.patch('apps.calepinage.selectors.resultat_servi', side_effect=interdit), \
                mock.patch('apps.calepinage.services.electrique.resultat_calepinage', side_effect=interdit), \
                mock.patch('apps.calepinage.services.electrique._simulation_servie', side_effect=interdit), \
                mock.patch.object(simulation, 'empreinte_simulation',
                                  wraps=simulation.empreinte_simulation) as empreinte:
            _requetes, reponse = self._compte(url)
        self.assertGreater(empreinte.call_count, 0)  # la fraîcheur a bien été jugée
        self.assertIn(['simulation_perimee'], [ligne['signaux'] for ligne in reponse.data['lignes']])

    def test_la_file_a_traiter_garde_les_signaux_du_resultat_servi(self):
        """Lane I4 — pour chaque dossier de la file simulée, les signaux coûteux lus sur le
        stocké sont CEUX que donnait le résultat servi entier, et la réponse est identique."""
        from apps.calepinage import selectors
        from apps.calepinage.services import assistant

        def avant(calepinage):
            servi = selectors.resultat_servi(calepinage) or {}
            return assistant._bloc_production(servi)[3] + assistant._bloc_electrique(calepinage)[1]

        semer_file_simulee(self, self._devis)
        vus = set()
        for calepinage in Calepinage.objects.filter(company=self.company, titre__startswith='Simulée'):
            servi = selectors.resultat_servi(calepinage)
            with self.subTest(calepinage=calepinage.titre):
                self.assertEqual(assistant._simulation_stockee(calepinage),
                                 {cle: servi[cle] for cle in ('simule', 'simulation_perimee')})
                self.assertEqual(sorted(assistant._signaux_couteux(calepinage)[0]), sorted(avant(calepinage)))
            vus.add((servi['simule'], servi['simulation_perimee']))
        self.assertEqual(vus, {(True, False), (False, True), (False, False)})  # frais, périmé, jamais
        url = '/api/django/calepinage/calepinages/a-traiter/?limite=19'
        apres = self.api.get(url).data
        with mock.patch.object(assistant, '_signaux_couteux', side_effect=lambda c: (avant(c), True)):
            self.assertEqual(self.api.get(url).data, apres)

    # ── Lane I4 — la file ne touche jamais le réseau (PVGIS TMY) ─────────────
    def _fournir_tmy(self, transport, cache=None):
        """Branche le VRAI ``temperatures_tmy`` sur un client au transport injecté (cache
        privé ou ``cache``) ; le fournisseur précédent est rendu en fin d'essai."""
        import functools

        from apps.calepinage.services.electrique import enregistrer_fournisseur_temperatures
        from apps.calepinage.services.temperatures_tmy import temperatures_tmy

        from .test_pvgis_serie import client

        options = {} if cache is None else {'cache': cache}
        precedent = enregistrer_fournisseur_temperatures(
            functools.partial(temperatures_tmy, client=client(transport, **options)))
        self.addCleanup(enregistrer_fournisseur_temperatures, precedent)

    def _file_au_verdict_espionne(self, vus):
        """La file, le verdict électrique RÉEL calculé (et noté dans ``vus``) mais son signal
        forcé à « bloquant » : ce qui en sort dit si la file l'a tenu pour jugé."""
        from apps.calepinage.services import assistant

        vrai = assistant._bloc_electrique

        def espion(calepinage, variante=None):
            vus[calepinage.pk] = vrai(calepinage, variante)[0]
            return vus[calepinage.pk], ['bloquant_electrique']

        with mock.patch.object(assistant, '_bloc_electrique', side_effect=espion):
            _requetes, reponse = self._compte('/api/django/calepinage/calepinages/a-traiter/?limite=19')
        return reponse.data['lignes']

    def test_la_file_a_traiter_ne_touche_jamais_le_reseau(self):
        """(a) + (c) : année type absente du cache ⇒ aucune requête, ligne NON évaluée, aucun
        signal électrique, le signal de simulation (stocké) reste ; (d) hors de la file, le
        même manque interroge PVGIS comme aujourd'hui."""
        from .test_pvgis_serie import TransportEnregistre

        semer_file_simulee(self, self._devis)
        transport = TransportEnregistre(erreur=OSError('la file a appelé PVGIS'))
        self._fournir_tmy(transport)
        vus = {}
        with mock.patch('socket.getaddrinfo', side_effect=AssertionError('la file a touché le réseau')):
            lignes = self._file_au_verdict_espionne(vus)
        self.assertEqual(transport.appels, [])
        self.assertEqual(len(vus), 5)  # le verdict a été calculé pour les COUTEUX_MAX premiers…
        self.assertTrue(lignes)
        self.assertEqual([ligne['evalue'] for ligne in lignes], [False] * len(lignes))  # …mais pas jugé
        self.assertFalse([ligne for ligne in lignes if 'bloquant_electrique' in ligne['signaux']])
        self.assertIn(['simulation_perimee'], [ligne['signaux'] for ligne in lignes])
        _requetes, _reponse = self._compte(_url(RESULTAT, next(iter(vus))))
        self.assertTrue(transport.appels)  # (d) : le détail interroge PVGIS sur un manque

    def test_la_file_a_traiter_juge_sur_une_annee_type_en_cache(self):
        """(b) : l'année type EN CACHE est servie dans la file — la ligne est évaluée et son
        verdict électrique est celui calculé hors de la file."""
        from apps.calepinage.services import assistant
        from apps.calepinage.services.pvgis_serie import _Cache

        from .test_pvgis_serie import TransportEnregistre, charger

        semer_file_simulee(self, self._devis)
        cache, rejoue = _Cache(), TransportEnregistre(charger('tmy_casablanca.json'))
        self._fournir_tmy(rejoue, cache)
        premiers = Calepinage.objects.filter(company=self.company).order_by('-updated_at', '-id')[:5]
        attendus = {calepinage.pk: assistant._bloc_electrique(calepinage)[0] for calepinage in premiers}
        self.assertEqual(len(rejoue.appels), 1)  # hors de la file : PVGIS (rejoué), mis en cache
        refus = TransportEnregistre(erreur=OSError('la file a appelé PVGIS'))
        self._fournir_tmy(refus, cache)
        vus = {}
        lignes = self._file_au_verdict_espionne(vus)
        self.assertEqual((refus.appels, vus), ([], attendus))
        evaluees = [ligne for ligne in lignes if ligne['evalue']]
        self.assertEqual(sorted(ligne['calepinage'] for ligne in evaluees), sorted(attendus))
        self.assertTrue(all('bloquant_electrique' in ligne['signaux'] for ligne in evaluees))
