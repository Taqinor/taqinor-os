"""ADEP8 (C-ADEP-003) — une pile copiée de ``.env.example`` garde le backend
e-mail CONSOLE et n'appelle aucune API d'envoi.

CLAUDE.md fait de « copy ``.env.example`` to ``.env`` first » LE chemin
d'installation. Le modèle publiait ``EMAIL_BACKEND=anymail...sendgrid`` actif :
toute pile locale (beat de relances, sondes qa-explorer) chargeait le vrai
backend SendGrid et, une clé collée, écrivait à de vrais clients.

Le test charge les réglages dans un interpréteur NEUF dont l'environnement est
celui que produit ``.env.example`` (les réglages sont déjà importés dans ce
processus-ci : seul un sous-processus rejoue honnêtement un démarrage).
Test-du-test : décommenter ``EMAIL_BACKEND`` dans ``.env.example`` ⇒ échec.
"""
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CONSOLE = 'django.core.mail.backends.console.EmailBackend'

#: Clés e-mail que l'environnement du processus de test ne doit pas souffler
#: au sous-processus : seul ``.env.example`` décide.
CLES_EMAIL = ('EMAIL_BACKEND', 'SENDGRID_API_KEY', 'BREVO_API_KEY')


def _env_example_path():
    # .../backend/django_core → racine du dépôt (deux niveaux au-dessus).
    return Path(settings.BASE_DIR).resolve().parents[1] / '.env.example'


def _lire_env_example(path):
    """Parse ``KEY=VALUE`` comme le fait ``env_file`` de docker compose."""
    valeurs = {}
    for ligne in path.read_text(encoding='utf-8').splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#') or '=' not in ligne:
            continue
        cle, valeur = ligne.split('=', 1)
        valeur = valeur.strip()
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in '"\'':
            valeur = valeur[1:-1]
        valeurs[cle.strip()] = valeur
    return valeurs


class EnvExempleTests(SimpleTestCase):
    def setUp(self):
        self.path = _env_example_path()
        if not self.path.exists():
            self.skipTest(f'.env.example introuvable : {self.path}')
        self.valeurs = _lire_env_example(self.path)

    def _charger(self):
        environnement = {k: v for k, v in os.environ.items()
                         if k not in CLES_EMAIL}
        environnement.update(self.valeurs)
        environnement['PYTHONIOENCODING'] = 'utf-8'
        acheve = subprocess.run(
            [sys.executable, '-c',
             'from django.conf import settings; '
             'print("EMAIL_BACKEND=" + settings.EMAIL_BACKEND)'],
            cwd=str(settings.BASE_DIR), env=environnement,
            capture_output=True, text=True, encoding='utf-8', errors='replace')
        sortie = (acheve.stdout or '') + (acheve.stderr or '')
        self.assertEqual(acheve.returncode, 0, sortie)
        for ligne in (acheve.stdout or '').splitlines():
            if ligne.startswith('EMAIL_BACKEND='):
                return ligne.split('=', 1)[1].strip()
        self.fail(f'EMAIL_BACKEND non imprimé : {sortie}')

    def test_env_exemple_ne_pose_aucun_backend_reel(self):
        self.assertNotIn(
            'EMAIL_BACKEND', self.valeurs,
            '.env.example ne doit pas activer de backend e-mail : la recette '
            'prod reste en commentaire (ADEP8).')
        self.assertNotIn('SENDGRID_API_KEY', self.valeurs)
        self.assertNotIn('BREVO_API_KEY', self.valeurs)

    def test_env_exemple_backend_console(self):
        self.assertEqual(self._charger(), CONSOLE)
