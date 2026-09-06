"""AUD411 — la couche `prod.py` ENTIÈRE, pas seulement `DEBUG` (re-scope QJR423).

QJR423 ne regardait que ``DEBUG``. Le re-scope AUD411 : si la production charge
``settings.dev``, ce n'est pas seulement la trace DEBUG qui manque —
``SESSION/CSRF_COOKIE_SECURE``, ``SECURE_SSL_REDIRECT``, HSTS, le CORS
restrictif ET le garde ``RuntimeError`` sur ``SECRET_KEY`` (``prod.py`` /
``base.py``) sont TOUS morts. La chaîne d'indices : ``.env.example`` publie
``DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev`` + ``DJANGO_DEBUG=True``,
``docker-compose.yml`` passe ce ``.env`` en ``env_file`` sur tous les
conteneurs, donc la variable d'env prime sur le ``setdefault`` prod de
``wsgi.py``.

DEUX NIVEAUX, DÉLIBÉRÉMENT :

* **Erreur bloquante** quand le module de production EST chargé mais qu'un
  réglage de durcissement a été désarmé ;
* **Avertissement** (jamais bloquant) quand l'environnement se DÉCLARE
  production mais charge un autre module — le rendre bloquant COUPERAIT le
  service au premier redémarrage, AVANT la bascule
  ``DJANGO_SETTINGS_MODULE=erp_agentique.settings.prod``. L'écart est NOMMÉ au
  lieu de rester invisible.

MOITIÉ SERVEUR (hors dépôt) : la bascule du ``.env`` de production et la
vérification de santé complète ne sont pas testables ici — elles appartiennent
au déploiement.

Lancer :
    docker compose exec django_core python manage.py test \
        core.tests.test_aud411_couche_prod -v 2
"""
import os
from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.checks import (
    ID_DURCISSEMENT, ID_MODULE_NON_PROD, REGLAGES_DURCISSEMENT,
    module_de_production, verifier_couche_durcissement,
    verifier_reglages_production,
)

MODULE_DEV = 'erp_agentique.settings.dev'
MODULE_PROD = 'erp_agentique.settings.prod'

#: Un durcissement COMPLET, tel que `prod.py` le pose.
DURCI = {
    'SESSION_COOKIE_SECURE': True,
    'CSRF_COOKIE_SECURE': True,
    'SECURE_SSL_REDIRECT': True,
    'SECURE_CONTENT_TYPE_NOSNIFF': True,
    'CORS_ALLOW_ALL_ORIGINS': False,
    'SECURE_HSTS_SECONDS': 31536000,
}


def _ids(constats):
    return {c.id for c in constats}


def _module(nom):
    """Force le module de réglages VU par les contrôles."""
    return mock.patch.dict(os.environ, {'DJANGO_SETTINGS_MODULE': nom})


class LeModuleCharge(SimpleTestCase):
    """`module_de_production` distingue le MODULE de la simple intention."""

    def test_le_module_prod_est_reconnu(self):
        self.assertTrue(module_de_production(MODULE_PROD, environ={}))
        self.assertTrue(module_de_production(
            'erp_agentique.settings.production', environ={}))

    def test_le_module_dev_ne_l_est_pas(self):
        self.assertFalse(module_de_production(MODULE_DEV, environ={}))

    def test_une_variable_d_environnement_ne_suffit_pas(self):
        """C'est TOUT l'objet d'AUD411 : `DJANGO_ENV=prod` déclare une
        intention, mais c'est le MODULE chargé qui décide si la couche de
        durcissement existe réellement."""
        self.assertFalse(module_de_production(
            MODULE_DEV, environ={'DJANGO_ENV': 'production'}))


class LaCoucheDeDurcissement(SimpleTestCase):

    def test_module_dev_charge_produit_un_avertissement_non_bloquant(self):
        """ROUGE avant AUD411 : rien ne signalait que TOUTE la couche prod
        était inerte — seul DEBUG était regardé."""
        with _module(MODULE_DEV), override_settings(SETTINGS_MODULE=None):
            constats = verifier_couche_durcissement()
        self.assertEqual(_ids(constats), {ID_MODULE_NON_PROD})
        self.assertEqual(constats[0].level, 30)  # WARNING, jamais ERROR
        message = f'{constats[0].msg} {constats[0].hint}'
        for attendu in ('Secure', 'HSTS', 'CORS', 'SECRET_KEY',
                        'erp_agentique.settings.prod'):
            self.assertIn(attendu, message)

    def test_module_prod_durci_ne_produit_rien(self):
        with _module(MODULE_PROD), override_settings(
                SETTINGS_MODULE=None, **DURCI):
            self.assertEqual(verifier_couche_durcissement(), [])

    def test_chaque_reglage_desarme_est_une_erreur_bloquante(self):
        for reglage, attendu, _consequence in REGLAGES_DURCISSEMENT:
            with self.subTest(reglage=reglage):
                desarme = dict(DURCI)
                desarme[reglage] = not attendu
                with _module(MODULE_PROD), override_settings(
                        SETTINGS_MODULE=None, **desarme):
                    constats = verifier_couche_durcissement()
                self.assertEqual(_ids(constats), {ID_DURCISSEMENT})
                self.assertIn(reglage, constats[0].msg)
                self.assertEqual(constats[0].level, 40)  # ERROR (bloquant)

    def test_hsts_nul_est_une_erreur_bloquante(self):
        sans_hsts = dict(DURCI, SECURE_HSTS_SECONDS=0)
        with _module(MODULE_PROD), override_settings(
                SETTINGS_MODULE=None, **sans_hsts):
            constats = verifier_couche_durcissement()
        self.assertEqual(_ids(constats), {ID_DURCISSEMENT})
        self.assertIn('SECURE_HSTS_SECONDS', constats[0].msg)

    def test_branche_dans_le_controle_systeme_de_production(self):
        """Le contrôle enregistré (`@register(Tags.security)`) l'inclut."""
        with _module(MODULE_PROD), override_settings(
                SETTINGS_MODULE=None, DEBUG=False,
                ALLOWED_HOSTS=['api.taqinor.ma'],
                **dict(DURCI, SESSION_COOKIE_SECURE=False)):
            constats = verifier_reglages_production()
        self.assertIn(ID_DURCISSEMENT, _ids(constats))


class HorsProductionCEstUnNoOp(SimpleTestCase):
    """Le développement et la CI (qui tournent sur `settings.dev`) sont
    strictement inchangés : le contrôle enregistré rend une liste vide."""

    def test_developpement_inchange(self):
        with mock.patch.dict(os.environ,
                             {'DJANGO_SETTINGS_MODULE': MODULE_DEV},
                             clear=False):
            for variable in ('DJANGO_ENV', 'ENVIRONMENT', 'APP_ENV', 'ENV'):
                os.environ.pop(variable, None)
            with override_settings(SETTINGS_MODULE=None, DEBUG=True):
                self.assertEqual(verifier_reglages_production(), [])
