"""TCH111 — les 19 actions du Copilote sur les tâches (reference/api.md §8 ; regles.md §8, §12).

Sans base : chaque action est au registre, attribuée au module, gardée par `taches_voir` comme sa route,
lot `copilote`, `internal`, et sa méthode est servie par une route CONSTRUITE de l'app. Avec base (CI) :
les échos n'écrivent rien ; et le canari — un projet et ses tâches confidentiels portant « Canari »
partout — n'apparaît dans AUCUNE réponse servie à l'assistant, quelle que soit l'action.
"""
import datetime
import json
import re

from django.test import SimpleTestCase, TestCase
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient

from apps.agent import registry
from apps.taches import agent_actions
from apps.taches.tests import fabriques
from apps.taches.tests.test_meme_proprietaire import empreinte
from apps.taches.tests.test_routes import est_construite
from apps.taches.views.base import DROIT, PermissionTaches

#: Les 19 clés du tableau d'api.md §8, dans son ordre.
CLES = (
    'taches.journee.lire', 'taches.journee.prioriser', 'taches.journee.point', 'taches.plan.proposer',
    'taches.tache.chercher', 'taches.profil.lire', 'taches.projet.lire', 'taches.revue.semaine',
    'taches.tache.creer', 'taches.tache.terminer', 'taches.tache.modifier', 'taches.tache.planifier',
    'taches.rappel.poser', 'taches.projet.creer', 'taches.rythme.regler', 'taches.preference.noter',
    'taches.liste.ranger', 'taches.projet.planifier_apercu', 'taches.tache.proposer_changement',
)
#: ✎ et ⟲ du tableau d'api.md §8.
ECRITURES = {'taches.tache.creer', 'taches.tache.terminer', 'taches.tache.modifier', 'taches.tache.planifier',
             'taches.rappel.poser', 'taches.projet.creer', 'taches.rythme.regler', 'taches.preference.noter'}
ECHOS = {'taches.liste.ranger', 'taches.projet.planifier_apercu', 'taches.tache.proposer_changement'}
MODULE = 'apps.taches.agent_actions'
PREFIXE = '/api/django/taches/'
PARAMETRE = re.compile(r'\{([a-z_]+)\}')


def chemin_relatif(action):
    return action.endpoint[len(PREFIXE):]


class CatalogueTests(SimpleTestCase):
    """Le registre porte les 19 actions, telles qu'api.md §8 les déclare."""

    def test_les_19_cles_dans_l_ordre(self):
        self.assertEqual(tuple(a.key for a in agent_actions.ACTIONS), CLES)
        servies = {a.key: a for a in registry.all_actions()}
        for cle in CLES:
            self.assertIs(servies.get(cle), next(a for a in agent_actions.ACTIONS if a.key == cle), cle)

    def test_attribuees_au_module_pour_le_gatage(self):
        self.assertEqual(registry._DISCOVERED.get(MODULE), set(CLES))

    def test_droit_risque_lot_et_carte(self):
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                self.assertEqual(action.required_permission, DROIT)
                self.assertEqual(DROIT, 'taches_voir')
                self.assertEqual(action.risk, registry.RISK_INTERNAL)
                self.assertEqual(action.lot, registry.LOT_COPILOTE)
                self.assertIn(action.carte, registry.CARTES)
                self.assertEqual(action.objets, {})

    def test_methode_et_droit_egaux_a_la_route(self):
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                self.assertTrue(action.endpoint.startswith(PREFIXE))
                vue = resolve(PARAMETRE.sub('1', action.endpoint)).func.view_class
                self.assertTrue(callable(getattr(vue, action.method.lower(), None)), action.method)
                self.assertIn(PermissionTaches, vue.permission_classes)
                self.assertTrue(est_construite(action.method, chemin_relatif(action)), 'route encore 501')

    def test_parametres_de_chemin_requis(self):
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                requis = set(action.inputs.get('required', ()))
                proprietes = set(action.inputs['properties'])
                self.assertLessEqual(set(PARAMETRE.findall(action.endpoint)), requis)
                self.assertLessEqual(requis, proprietes)

    def test_ecritures_echos_et_lectures(self):
        self.assertEqual(agent_actions.ECRITURES, ECRITURES)
        self.assertEqual(agent_actions.ECHOS, ECHOS)
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                lecture = action.key not in ECRITURES | ECHOS
                self.assertEqual(action.method == 'GET', lecture)

    def test_trois_ecritures_par_tour_au_plus(self):
        self.assertEqual(agent_actions.ECRITURES_PAR_TOUR, 3)
        creer = next(a for a in agent_actions.ACTIONS if a.key == 'taches.tache.creer')
        self.assertIn('trois par tour au plus', creer.description)

    def test_ranger_n_est_jamais_une_creation(self):
        ranger = next(a for a in agent_actions.ACTIONS if a.key == 'taches.liste.ranger')
        self.assertEqual(ranger.inputs['properties']['apercu']['enum'], [True])
        self.assertIn('apercu', ranger.inputs['required'])

    def test_descriptions_disent_a_quoi_sert_l_outil(self):
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                self.assertTrue(action.description.startswith('Sert à : '))
                self.assertLessEqual(len(action.description.split()), 40)

    def test_enregistrement_idempotent(self):
        avant = {a.key for a in registry.all_actions()}
        agent_actions.register_actions()
        self.assertEqual({a.key for a in registry.all_actions()}, avant)


# --- Avec base (CI) ------------------------------------------------------------------------------

def _client(compte):
    client = APIClient()
    client.force_authenticate(compte)
    return client


def _appeler(client, action, entrees, **entetes):
    """Appelle la route de l'action comme le relais : chemin rempli, reste en requête (GET) ou en
    corps JSON."""
    entrees = dict(entrees)
    chemin = PARAMETRE.sub(lambda m: str(entrees.pop(m.group(1))), action.endpoint)
    if action.method == 'GET':
        return client.get(chemin, entrees, **entetes)
    return getattr(client, action.method.lower())(chemin, entrees, format='json', **entetes)


def _iso(jour):
    return jour.isoformat()


class EchosSansEcritureTests(TestCase):
    """⟲ : un aperçu, jamais une ligne écrite (projet non confidentiel : la route répond 200)."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('echos'))
        fabriques.reglages(cls.compte)
        cls.projet = fabriques.projet(cls.compte, nom='Chantier Benali')
        cls.tache = fabriques.tache(cls.compte, projet=cls.projet, jour_prevu=timezone.localdate())
        fabriques.tache(cls.compte, titre='Appeler Lydec')  # À trier

    def test_aucun_echo_n_ecrit(self):
        entrees = {
            'taches.liste.ranger': {'texte': 'appeler le fournisseur\nrelancer le devis', 'apercu': True},
            'taches.projet.planifier_apercu': {'id': self.projet.pk, 'texte': 'Études :\nVisite'},
            'taches.tache.proposer_changement': {'id': self.tache.pk, 'geste': 'renommer', 'titre': 'Devis'},
        }
        par_cle = {a.key: a for a in agent_actions.ACTIONS}
        for cle in ECHOS:
            with self.subTest(cle=cle):
                avant = empreinte()
                reponse = _appeler(_client(self.compte), par_cle[cle], entrees[cle], HTTP_X_TAQINOR_ASSISTANT='1')
                self.assertEqual(reponse.status_code, 200, reponse.content[:300])
                self.assertEqual(empreinte(), avant)


class CanariTests(TestCase):
    """regles.md §8 : sous l'en-tête assistant, aucune des 19 routes ne sert un mot d'un objet
    confidentiel ; à l'écran, le canari est vivant."""

    @classmethod
    def setUpTestData(cls):
        cls.jour = timezone.localdate()
        cls.compte = fabriques.compte(fabriques.societe('canari-agent'))
        fabriques.reglages(cls.compte)
        cls.projet = fabriques.projet(cls.compte, nom='Canari-projet', objectif='Canari-objectif',
                                      domaine='Canari-dom', confidentiel=True)
        etape = fabriques.section(cls.projet, nom='Canari-étape')
        cls.taches = [
            fabriques.tache(cls.compte, projet=cls.projet, section=etape, titre=f'Canari-titre-{n}',
                            notes='Canari-notes', jour_prevu=cls.jour)
            for n in range(5)]
        fabriques.tache(cls.compte, projet=cls.projet, titre='Canari-titre-tour')

    def _entrees(self):
        t = self.taches
        return {
            'taches.journee.lire': {}, 'taches.journee.prioriser': {}, 'taches.journee.point': {},
            'taches.plan.proposer': {}, 'taches.tache.chercher': {'q': 'Canari'}, 'taches.profil.lire': {},
            'taches.projet.lire': {'id': self.projet.pk}, 'taches.revue.semaine': {},
            'taches.tache.creer': {'titre': 'Nouvelle tâche', 'projet_id': self.projet.pk},
            'taches.tache.terminer': {'id': t[0].pk},
            'taches.tache.modifier': {'id': t[1].pk, 'lock_version': t[1].lock_version, 'priorite': 3},
            'taches.tache.planifier': {'id': t[2].pk, 'lock_version': t[2].lock_version,
                                       'jour_prevu': _iso(self.jour + datetime.timedelta(days=3))},
            'taches.rappel.poser': {'id': t[3].pk, 'jour': _iso(self.jour + datetime.timedelta(days=1)),
                                    'heure': '10:00'},
            'taches.projet.creer': {'nom': 'Projet neuf'},
            'taches.rythme.regler': {'mode': 'pousser', 'objectif': 7},
            'taches.preference.noter': {'cle': 'heure_limite', 'valeur': '19:00'},
            'taches.liste.ranger': {'texte': 'appeler le fournisseur', 'apercu': True},
            'taches.projet.planifier_apercu': {'id': self.projet.pk, 'texte': 'Visite'},
            'taches.tache.proposer_changement': {'id': t[4].pk, 'geste': 'abandonner'},
        }

    def test_aucune_action_ne_sert_le_canari_a_l_assistant(self):
        entrees = self._entrees()
        self.assertEqual(set(entrees), set(CLES))
        client = _client(self.compte)
        for action in agent_actions.ACTIONS:
            with self.subTest(cle=action.key):
                self.assertLessEqual(set(entrees[action.key]), set(action.inputs['properties']))
                reponse = _appeler(client, action, entrees[action.key], HTTP_X_TAQINOR_ASSISTANT='1')
                # Projet confidentiel : l'assistant ne lit pas sa liste (403, sans un mot du projet).
                attendu = (403,) if action.key == 'taches.projet.planifier_apercu' else (200, 201)
                self.assertIn(reponse.status_code, attendu, reponse.content[:300])
                corps = json.dumps(reponse.json(), ensure_ascii=False).lower()
                self.assertNotIn('canari', corps)

    def test_a_l_ecran_le_canari_est_vivant(self):
        action = next(a for a in agent_actions.ACTIONS if a.key == 'taches.journee.lire')
        reponse = _appeler(_client(self.compte), action, {})
        self.assertIn('Canari-titre-0', reponse.content.decode('utf-8'))


# --- TCH164 : `taches.tache.modifier` (A18-M3 c ; regles.md §12) ----------------------------------

MODIFIER = next(a for a in agent_actions.ACTIONS if a.key == 'taches.tache.modifier')


class ModifierSansBaseTests(SimpleTestCase):
    def test_trois_champs_seulement_et_verrou_requis(self):
        self.assertEqual(agent_actions.CHAMPS_MODIFIABLES, ('priorite', 'echeance', 'projet_id'))
        self.assertEqual(set(MODIFIER.inputs['properties']),
                         {'id', 'lock_version', *agent_actions.CHAMPS_MODIFIABLES})
        self.assertEqual(set(MODIFIER.inputs['required']), {'id', 'lock_version'})
        self.assertEqual((MODIFIER.method, MODIFIER.endpoint), ('PATCH', '/api/django/taches/taches/{id}/'))

    def test_sur_demande_explicite_et_jamais_sous_un_texte_tiers(self):
        # Écriture : comptée dans les trois par tour, et rendue en carte-écho par le relais dès qu'un
        # texte tiers est entré dans le tour (A5) — jamais exécutée sur ce texte.
        self.assertIn(MODIFIER.key, agent_actions.ECRITURES)
        self.assertNotIn(MODIFIER.key, agent_actions.ECHOS)
        self.assertEqual(MODIFIER.carte, 'tache')
        self.assertIn('demande explicite', MODIFIER.description)
        self.assertIn('jamais sur un texte lu ou collé', MODIFIER.description)


class ModifierTests(TestCase):
    """PATCH à verrou : `lock_version` requis, version périmée refusée, geste annulable."""

    @classmethod
    def setUpTestData(cls):
        cls.compte = fabriques.compte(fabriques.societe('modifier'))
        fabriques.reglages(cls.compte)
        cls.admin = fabriques.projet(cls.compte, nom='Admin', priorite=1)
        cls.ventes = fabriques.projet(cls.compte, nom='Ventes', priorite=3)
        cls.tva = fabriques.tache(cls.compte, projet=cls.admin, titre='Déclaration TVA')

    def _modifier(self, **entrees):
        entrees.setdefault('id', self.tva.pk)
        return _appeler(_client(self.compte), MODIFIER, entrees, HTTP_X_TAQINOR_ASSISTANT='1')

    def test_sans_verrou_400_rien_ecrit(self):
        avant = empreinte()
        reponse = self._modifier(priorite=3)
        self.assertEqual(reponse.status_code, 400, reponse.content[:300])
        self.assertEqual(empreinte(), avant)

    def test_version_perimee_409_rien_ecrit(self):
        avant = empreinte()
        reponse = self._modifier(priorite=3, lock_version=self.tva.lock_version + 5)
        self.assertEqual(reponse.status_code, 409, reponse.content[:300])
        self.assertEqual(empreinte(), avant)

    def test_modifiee_puis_annulee(self):
        from apps.taches.models.taches import Tache
        echeance = timezone.localdate() + datetime.timedelta(days=2)
        reponse = self._modifier(priorite=3, echeance=_iso(echeance), projet_id=self.ventes.pk,
                                 lock_version=self.tva.lock_version)
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        geste_id = reponse.json()['geste_id']
        self.assertIsNotNone(geste_id)
        tva = Tache.objects.get(pk=self.tva.pk)
        self.assertEqual((tva.priorite, tva.echeance, tva.projet_id), (3, echeance, self.ventes.pk))
        annule = _client(self.compte).post(f'/api/django/taches/gestes/{geste_id}/annuler/', {}, format='json')
        self.assertEqual(annule.status_code, 200, annule.content[:300])
        tva.refresh_from_db()
        self.assertEqual((tva.priorite, tva.echeance, tva.projet_id), (0, None, self.admin.pk))
