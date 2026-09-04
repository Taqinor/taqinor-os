"""SOL3 — les DEUX éditions démarrent (`manage.py check`) et sont cohérentes.

La gate PR tourne en édition ``full`` : le processus de test EST déjà la preuve
que l'édition complète démarre. Ce qu'il reste à prouver, c'est que l'édition
``solar`` — celle que vise la PRODUCTION — démarre elle aussi, avec les sept
verticaux réellement absents d'INSTALLED_APPS, de l'arbre d'urls et du planning
Celery beat.

On lance donc un SOUS-PROCESSUS ``manage.py verifier_edition`` par édition.
Cette commande hérite du ``requires_system_checks`` par défaut de Django : elle
exécute donc TOUS les system checks (le `manage.py check` demandé) AVANT sa
propre vérification de cohérence. Un vertical parqué qui resterait monté fait
échouer la commande, donc le test.
"""
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from erp_agentique.settings import editions

_MANAGE = Path(settings.BASE_DIR) / 'manage.py'


def _env_edition(edition):
    env = dict(os.environ)
    env['TAQINOR_EDITION'] = edition
    # Sortie du fils en UTF-8 : les libellés du registre sont accentués et le
    # test les compare littéralement (sinon faux rouge sous Windows).
    env['PYTHONIOENCODING'] = 'utf-8'
    env.setdefault(
        'DJANGO_SETTINGS_MODULE',
        os.environ.get('DJANGO_SETTINGS_MODULE',
                       'erp_agentique.settings.dev'))
    return env


def _lancer_verifier_edition(edition, timeout=300):
    return subprocess.run(
        [sys.executable, str(_MANAGE), 'verifier_edition'],
        cwd=str(settings.BASE_DIR),
        env=_env_edition(edition), capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=timeout,
    )


class BootDesDeuxEditionsTests(SimpleTestCase):
    """Un sous-processus par édition — pas de base de données nécessaire."""

    def test_manage_py_present(self):
        self.assertTrue(_MANAGE.exists(), f'manage.py introuvable : {_MANAGE}')

    def test_edition_complete_demarre_et_est_coherente(self):
        res = _lancer_verifier_edition(editions.EDITION_FULL)
        self.assertEqual(
            res.returncode, 0,
            f'édition full : boot/cohérence KO\nSTDOUT:\n{res.stdout}\n'
            f'STDERR:\n{res.stderr}')
        self.assertIn('Édition chargée : full', res.stdout)
        self.assertIn('cohérente', res.stdout)

    def test_edition_solaire_demarre_et_parque_les_sept_verticaux(self):
        res = _lancer_verifier_edition(editions.EDITION_SOLAR)
        self.assertEqual(
            res.returncode, 0,
            f'édition solar : boot/cohérence KO\nSTDOUT:\n{res.stdout}\n'
            f'STDERR:\n{res.stderr}')
        self.assertIn('Édition chargée : solar', res.stdout)
        for libelle in editions.apps_parquees(editions.EDITION_SOLAR).values():
            self.assertIn(libelle, res.stdout)
        self.assertIn('cohérente', res.stdout)

    def test_edition_inconnue_refuse_de_demarrer(self):
        """Une coquille ne doit JAMAIS retomber en silence sur `full`."""
        res = subprocess.run(
            [sys.executable, str(_MANAGE), 'verifier_edition'],
            cwd=str(settings.BASE_DIR),
            env=_env_edition('solaire'), capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=300)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn('solaire', res.stdout + res.stderr)


class UrlsSelonEditionTests(SimpleTestCase):
    def test_helper_monte_ou_non_selon_l_edition(self):
        from erp_agentique import urls as urls_module

        # App gardée : toujours montée, quelle que soit l'édition.
        self.assertEqual(
            len(urls_module._si_active('crm/', 'apps.crm.urls')), 1)

    def test_arbre_urls_de_l_edition_courante_sans_app_parquee(self):
        from core.management.commands.verifier_edition import (
            _modules_de_l_arbre_urls,
        )

        montes = _modules_de_l_arbre_urls()
        edition = settings.TAQINOR_EDITION
        fuites = [
            nom for nom in montes
            if editions.est_module_parque(nom, edition)
        ]
        self.assertEqual(fuites, [])
        if edition == editions.EDITION_FULL:
            # Non-régression : en édition complète TOUT reste monté.
            self.assertIn('apps.mrp.urls', montes)
            self.assertIn('apps.education.public_urls', montes)

    def test_installed_apps_coherent_avec_l_edition_courante(self):
        parquees = set(editions.apps_parquees(settings.TAQINOR_EDITION))
        self.assertEqual(set(settings.INSTALLED_APPS) & parquees, set())
