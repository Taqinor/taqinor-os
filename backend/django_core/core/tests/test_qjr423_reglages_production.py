"""QJR423 / DR8 — la production ne peut plus démarrer en mode DEBUG, et ses
réglages d'exposition sont revus.

PRÉMISSE CORRIGÉE, à ne pas rejouer : ``settings/prod.py`` porte DÉJÀ
``DEBUG = False`` en dur. Il n'y a rien à « couper » dans le code — ce qui
n'était garanti nulle part, c'est que la production charge bien CE module.
La tâche ferme le trou par trois moyens :

  1. un contrôle système qui REFUSE le démarrage quand ``DEBUG`` est vrai
     alors que l'environnement se déclare production ;
  2. ``ALLOWED_HOSTS`` explicite et non permissif exigé en production
     (refusé au défaut ``localhost,127.0.0.1`` de ``base.py``), accepté en
     développement ;
  3. un ``LOGGING`` configuré dans ``prod.py``, pour qu'un incident soit
     lisible SANS rallumer DEBUG.

La configuration de DÉVELOPPEMENT reste inchangée : hors production, les
contrôles rendent une liste vide.

Lancer :
    docker compose exec django_core python manage.py test \
        core.tests.test_qjr423_reglages_production -v 2
"""
import importlib
import os
from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.checks import (
    ID_ALLOWED_HOSTS, ID_DEBUG, allowed_hosts_permissif,
    environnement_de_production, verifier_reglages_production)

MODULE_DEV = 'erp_agentique.settings.dev'
MODULE_PROD = 'erp_agentique.settings.prod'


def _prod_env():
    """Un environnement qui SE DÉCLARE production, sans toucher au reste."""
    return mock.patch.dict(os.environ, {'DJANGO_ENV': 'production'})


def _ids(erreurs):
    return {e.id for e in erreurs}


class LEnvironnementDeProductionEstReconnu(SimpleTestCase):
    """La déclaration « production » vient du module de réglages OU d'une
    variable d'environnement — l'une ou l'autre suffit."""

    def test_le_module_prod_se_declare_production(self):
        self.assertTrue(
            environnement_de_production(MODULE_PROD, environ={}))
        self.assertTrue(
            environnement_de_production(
                'erp_agentique.settings.production', environ={}))

    def test_le_module_dev_ne_se_declare_pas_production(self):
        self.assertFalse(environnement_de_production(MODULE_DEV, environ={}))

    def test_une_variable_d_environnement_suffit(self):
        for variable in ('DJANGO_ENV', 'ENVIRONMENT', 'APP_ENV', 'ENV'):
            with self.subTest(variable=variable):
                self.assertTrue(environnement_de_production(
                    MODULE_DEV, environ={variable: 'production'}))
                self.assertTrue(environnement_de_production(
                    MODULE_DEV, environ={variable: 'PROD'}))

    def test_une_valeur_quelconque_ne_declare_rien(self):
        self.assertFalse(environnement_de_production(
            MODULE_DEV, environ={'DJANGO_ENV': 'staging'}))


class UneProductionEnDebugRefuseDeDemarrer(SimpleTestCase):
    """LE TEST ROUGE — aujourd'hui elle démarre."""

    @override_settings(DEBUG=True, ALLOWED_HOSTS=['api.taqinor.ma'])
    def test_debug_vrai_en_production_est_une_erreur_bloquante(self):
        with _prod_env():
            erreurs = verifier_reglages_production()

        self.assertIn(
            ID_DEBUG, _ids(erreurs),
            'une production en DEBUG doit refuser de démarrer : le contrôle '
            "système est absent ou n'a pas vu la déclaration production.")
        faute = next(e for e in erreurs if e.id == ID_DEBUG)
        self.assertIn(
            'DEBUG', faute.msg,
            'le message doit NOMMER le réglage fautif.')

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['api.taqinor.ma'])
    def test_une_production_bien_reglee_ne_bloque_rien(self):
        with _prod_env():
            self.assertEqual(verifier_reglages_production(), [])


class AllowedHostsExigeDesDomainesExplicites(SimpleTestCase):
    """Second test du `Done =` — refusé en production, accepté en dev."""

    PERMISSIFS = (
        [],
        ['localhost', '127.0.0.1'],   # le défaut hérité de base.py
        ['localhost'],
        ['*'],
        ['api.taqinor.ma', '*'],      # un joker suffit à tout ouvrir
    )
    EXPLICITES = (
        ['api.taqinor.ma'],
        ['api.taqinor.ma', 'localhost'],   # un hôte réel à côté du local : OK
        ['.taqinor.ma'],                   # sous-domaines, pas un joker
    )

    def test_le_predicat_distingue_permissif_et_explicite(self):
        for hotes in self.PERMISSIFS:
            with self.subTest(hotes=hotes):
                self.assertTrue(allowed_hosts_permissif(hotes))
        for hotes in self.EXPLICITES:
            with self.subTest(hotes=hotes):
                self.assertFalse(allowed_hosts_permissif(hotes))

    def test_le_defaut_permissif_est_refuse_en_production(self):
        with override_settings(DEBUG=False,
                               ALLOWED_HOSTS=['localhost', '127.0.0.1']):
            with _prod_env():
                erreurs = verifier_reglages_production()
        self.assertIn(ID_ALLOWED_HOSTS, _ids(erreurs))
        faute = next(e for e in erreurs if e.id == ID_ALLOWED_HOSTS)
        self.assertIn('ALLOWED_HOSTS', faute.msg)

    def test_le_meme_defaut_est_accepte_en_developpement(self):
        """Aucun run local ne doit être gêné."""
        with override_settings(DEBUG=True,
                               ALLOWED_HOSTS=['localhost', '127.0.0.1']):
            with mock.patch.dict(os.environ,
                                 {'DJANGO_ENV': '', 'ENVIRONMENT': '',
                                  'APP_ENV': '', 'ENV': ''}):
                self.assertEqual(verifier_reglages_production(), [])


class LaConfigurationDeDeveloppementEstInchangee(SimpleTestCase):
    """Troisième test du `Done =`."""

    def test_hors_production_le_controle_est_un_no_op_total(self):
        with override_settings(DEBUG=True, ALLOWED_HOSTS=[]):
            with mock.patch.dict(os.environ,
                                 {'DJANGO_ENV': '', 'ENVIRONMENT': '',
                                  'APP_ENV': '', 'ENV': ''}):
                self.assertEqual(verifier_reglages_production(), [])

    def test_dev_garde_son_propre_logging_et_son_debug(self):
        dev = importlib.import_module(MODULE_DEV)
        self.assertTrue(dev.DEBUG)
        self.assertIn('console', dev.LOGGING['handlers'])
        self.assertEqual(
            dev.LOGGING['loggers']['django']['level'], 'WARNING',
            'la configuration de développement doit rester inchangée.')


class LaProductionEstLisibleSansDebug(SimpleTestCase):
    """Troisième volet de la tâche — ``LOGGING`` configuré dans prod.py."""

    def test_prod_configure_le_logging(self):
        prod = importlib.import_module(MODULE_PROD)
        logging_conf = getattr(prod, 'LOGGING', None)
        self.assertTrue(
            logging_conf,
            "prod.py ne configure aucun LOGGING : un incident n'est lisible "
            "qu'en rallumant DEBUG, ce que le contrôle système interdit.")
        self.assertTrue(logging_conf.get('handlers'))
        self.assertIn('django.request', logging_conf.get('loggers', {}))

    def test_prod_porte_toujours_debug_false(self):
        prod = importlib.import_module(MODULE_PROD)
        self.assertFalse(prod.DEBUG)
