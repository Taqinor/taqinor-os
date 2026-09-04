"""AUD410 — un secret resté au PLACEHOLDER PUBLIÉ du dépôt ne démarre plus.

LE TROU. ``base.py`` ne rejetait que deux valeurs : la chaîne vide et le
littéral ``django-insecure-change-me``. Or ``.env.example`` publie
``DJANGO_SECRET_KEY=change_me_generate_with_python_secrets`` (et
``MINIO_ROOT_PASSWORD=change_me_in_production``, sans aucun garde), et
``CLAUDE.md`` fait de « copy ``.env.example`` to ``.env`` first » LE chemin
d'installation documenté. Une instance déployée depuis le modèle démarrait donc
en production avec une clé de signature JWT lisible par quiconque ouvre le
dépôt — forge de jetons triviale, rejouée par chaque nouvelle instance SaaS.

CE QUI EST VÉRIFIÉ ICI, dans l'ordre du ``Done =`` de la tâche :

  1. le TEST ROUGE : un démarrage réel (sous-processus) avec
     ``DJANGO_SECRET_KEY=change_me_generate_with_python_secrets`` et
     ``DEBUG=False`` réussissait ; il lève désormais ``RuntimeError`` ;
  2. une VRAIE clé générée démarre toujours — le garde ne casse rien ;
  3. le contrôle système QJR423 (``core/checks.py``, étendu et non doublé)
     attrape en plus le cas que le garde de ``base.py`` ne voit pas : une
     production qui se déclare telle mais tourne encore avec
     ``DJANGO_DEBUG=True`` (l'état réel constaté par AUD411), et il couvre
     ``MINIO_ROOT_PASSWORD`` qui n'avait aucun garde ;
  4. aucun message ne recopie la valeur du secret.

Lancer :
    docker compose exec django_core python manage.py test \
        core.tests.test_aud410_secrets_placeholder -v 2
"""
import os
import subprocess
import sys
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.checks import (
    ID_MINIO, ID_SECRET_KEY, secret_est_placeholder,
    verifier_reglages_production)
from erp_agentique.settings import placeholders

#: La valeur EXACTE publiée par ``.env.example`` pour la clé Django.
CLE_PUBLIEE = 'change_me_generate_with_python_secrets'

#: La valeur EXACTE publiée par ``.env.example`` pour le stockage d'objets.
MINIO_PUBLIE = 'change_me_in_production'

#: Une clé réellement générée par ``get_random_secret_key()``.
CLE_REELLE = 'k9#z2m-qv4t8_w1x!e6r%b0n$c7y+a3s(d5f)g8h2j4l6p9q'


def _demarrer(secret_key, debug='False'):
    """Démarre un interpréteur NEUF qui charge les réglages de production.

    Renvoie ``(code_retour, sortie)``. Le sous-processus est le seul moyen
    honnête de rejouer un DÉMARRAGE : le garde de ``base.py`` s'exécute à
    l'import du module de réglages, qui est déjà chargé dans ce processus-ci.
    """
    environnement = dict(os.environ)
    environnement.update({
        'DJANGO_SETTINGS_MODULE': 'erp_agentique.settings.prod',
        'DJANGO_DEBUG': debug,
        'DJANGO_SECRET_KEY': secret_key,
        'DJANGO_ALLOWED_HOSTS': 'api.taqinor.ma',
        'PYTHONIOENCODING': 'utf-8',
    })
    acheve = subprocess.run(
        [sys.executable, '-c',
         'from django.conf import settings; settings.SECRET_KEY; '
         'print("DEMARRAGE_OK")'],
        cwd=str(settings.BASE_DIR), env=environnement,
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    return acheve.returncode, (acheve.stdout or '') + (acheve.stderr or '')


class LePredicatReconnaitLesPlaceholdersPublies(SimpleTestCase):
    """Le prédicat partagé — une seule définition pour les deux gardes."""

    PLACEHOLDERS = (
        '',
        '   ',
        None,
        'django-insecure-change-me',
        'change_me',
        CLE_PUBLIEE,
        MINIO_PUBLIE,
        'CHANGE_ME_IN_PRODUCTION',      # la casse ne sauve pas le placeholder
        '  change_me_in_production  ',  # les espaces non plus
    )
    VRAIS_SECRETS = (
        CLE_REELLE,
        'exchange_me_not_a_placeholder',   # « change_me » ailleurs qu'en tête
        'ma-cle-de-prod-2026',
    )

    def test_les_placeholders_publies_sont_reconnus(self):
        for valeur in self.PLACEHOLDERS:
            with self.subTest(valeur=valeur):
                self.assertTrue(placeholders.est_placeholder(valeur))
                self.assertTrue(secret_est_placeholder(valeur))

    def test_une_vraie_cle_n_est_jamais_prise_pour_un_placeholder(self):
        for valeur in self.VRAIS_SECRETS:
            with self.subTest(valeur=valeur):
                self.assertFalse(placeholders.est_placeholder(valeur))
                self.assertFalse(secret_est_placeholder(valeur))

    def test_le_garde_de_base_et_le_controle_systeme_partagent_la_definition(
            self):
        """Le ré-export de ``core.checks`` EST le prédicat des réglages."""
        self.assertIs(
            secret_est_placeholder('x'), placeholders.est_placeholder('x'))


class UnePrductionAuPlaceholderPublieRefuseDeDemarrer(SimpleTestCase):
    """LE TEST ROUGE du ``Done =`` — avant AUD410, ce démarrage réussissait."""

    def test_la_cle_publiee_par_env_example_ne_demarre_plus(self):
        code, sortie = _demarrer(CLE_PUBLIEE)
        self.assertNotEqual(
            code, 0,
            'une production démarrée avec la clé publiée par .env.example '
            f'doit lever RuntimeError. Sortie observée :\n{sortie}')
        self.assertIn('RuntimeError', sortie)
        self.assertIn('DJANGO_SECRET_KEY', sortie)

    def test_le_placeholder_historique_est_toujours_refuse(self):
        code, _ = _demarrer('django-insecure-change-me')
        self.assertNotEqual(code, 0)

    def test_une_cle_vide_est_toujours_refusee(self):
        code, _ = _demarrer('')
        self.assertNotEqual(code, 0)

    def test_une_vraie_cle_demarre_toujours(self):
        """Le garde ne doit casser AUCUNE production correctement réglée."""
        code, sortie = _demarrer(CLE_REELLE)
        self.assertEqual(
            code, 0,
            f'une vraie clé générée doit démarrer. Sortie :\n{sortie}')
        self.assertIn('DEMARRAGE_OK', sortie)


class LeControleSystemeCouvreCeQueLeGardeDeBaseNeVoitPas(SimpleTestCase):
    """QJR423 étendu (jamais doublé) : le cas ``DEBUG=True`` en production, et
    ``MINIO_ROOT_PASSWORD`` qui n'avait aucun garde."""

    def _prod(self):
        return mock.patch.dict(os.environ, {'DJANGO_ENV': 'production'})

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['api.taqinor.ma'],
                       SECRET_KEY=CLE_PUBLIEE, MINIO_SECRET_KEY=CLE_REELLE)
    def test_la_cle_publiee_est_une_erreur_bloquante(self):
        with self._prod():
            erreurs = verifier_reglages_production()
        self.assertIn(ID_SECRET_KEY, {e.id for e in erreurs})

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['api.taqinor.ma'],
                       SECRET_KEY=CLE_REELLE, MINIO_SECRET_KEY=MINIO_PUBLIE)
    def test_le_mot_de_passe_minio_publie_est_une_erreur_bloquante(self):
        with self._prod():
            erreurs = verifier_reglages_production()
        self.assertIn(
            ID_MINIO, {e.id for e in erreurs},
            'MINIO_ROOT_PASSWORD=change_me_in_production est publié par '
            ".env.example et n'était protégé par aucun garde.")

    @override_settings(DEBUG=True, ALLOWED_HOSTS=['api.taqinor.ma'],
                       SECRET_KEY=CLE_PUBLIEE, MINIO_SECRET_KEY=CLE_REELLE)
    def test_le_cas_que_base_py_ne_voit_pas_est_attrape_ici(self):
        """``base.py`` ne teste la clé que si ``DJANGO_DEBUG`` est faux ; une
        production encore en DEBUG (état AUD411) lui échappe entièrement."""
        with self._prod():
            erreurs = verifier_reglages_production()
        self.assertIn(ID_SECRET_KEY, {e.id for e in erreurs})

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['api.taqinor.ma'],
                       SECRET_KEY=CLE_REELLE, MINIO_SECRET_KEY=CLE_REELLE)
    def test_une_production_bien_reglee_ne_bloque_rien(self):
        with self._prod():
            self.assertEqual(verifier_reglages_production(), [])

    @override_settings(DEBUG=True, ALLOWED_HOSTS=['localhost', '127.0.0.1'],
                       SECRET_KEY=CLE_PUBLIEE, MINIO_SECRET_KEY=MINIO_PUBLIE)
    def test_hors_production_c_est_un_no_op_total(self):
        """Le développement et la CI (settings.dev) restent inchangés."""
        with mock.patch.dict(os.environ,
                             {'DJANGO_ENV': '', 'ENVIRONMENT': '',
                              'APP_ENV': '', 'ENV': ''}):
            self.assertEqual(verifier_reglages_production(), [])

    @override_settings(DEBUG=False, ALLOWED_HOSTS=['api.taqinor.ma'],
                       SECRET_KEY=CLE_PUBLIEE, MINIO_SECRET_KEY=MINIO_PUBLIE)
    def test_aucun_message_ne_recopie_la_valeur_du_secret(self):
        with self._prod():
            erreurs = verifier_reglages_production()
        self.assertTrue(erreurs)
        for erreur in erreurs:
            texte = f'{erreur.msg} {erreur.hint}'
            self.assertNotIn(CLE_PUBLIEE, texte)
            self.assertNotIn(MINIO_PUBLIE, texte)
