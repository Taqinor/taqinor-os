"""VAO15 — le CONTRAT DE PURETÉ du paquet ``portail``, transformé en garde.

Un contrat écrit dans une docstring se perd à la troisième livraison. Ce
module le rend exécutable : il relit l'**arbre syntaxique** de chaque module
du paquet (jamais une simple recherche de texte, qui confondrait un import
avec le mot dans un commentaire) et rougit si :

  * un module — n'importe lequel, y compris le client — importe ``django``,
    ``rest_framework``, ``celery``, ``apps.*`` ou ``core.*`` : le collecteur
    doit rester testable sans base, donc sans Django ;
  * un module PUR (tout sauf ``client.py`` et ``detail.py``, les deux
    frontières réseau assumées) importe un client HTTP ou une pile réseau ;
  * un module PUR touche au disque (``open()``, ``pathlib``, ``tempfile``…) ;
  * un module de collecte importe le chargeur de fixtures — un parseur qui
    lit un fichier n'est plus un parseur pur.

L'analyseur est vérifié SUR LUI-MÊME (``AnalyseurTests``) : on lui donne des
sources fautives fabriquées et on exige qu'il les refuse. Sans cela, une garde
peut rester verte parce qu'elle ne voit plus rien.

Le paquet est enfin passé au crible D'EXÉCUTION : charger les fixtures et
manipuler leur contenu ne doit ouvrir AUCUNE socket (``GardeReseau``, que les
tests des tâches suivantes réutilisent).
"""
from __future__ import annotations

import ast
import socket
from pathlib import Path

from django.test import SimpleTestCase

from apps.veille_ao.portail import ErreurPortail, fixtures

PAQUET = Path(fixtures.DOSSIER).parent

#: Les deux SEULS modules autorisés à parler au réseau. Toute autre porte de
#: sortie est une régression : c'est la définition même de « le client HTTP
#: est la seule frontière réseau ».
MODULES_RESEAU = frozenset({'client.py', 'detail.py'})

#: Le chargeur de fixtures est un support de TEST : il lit le disque, et c'est
#: pour cela qu'il est le seul exclu du volet « aucune E/S ».
SUPPORT_DE_TEST = frozenset({'fixtures'})

#: Interdits PARTOUT dans le paquet, client compris.
CADRES_INTERDITS = ('django', 'rest_framework', 'celery', 'apps', 'core')

#: L'exception nommée : ``urllib.parse`` est de l'analyse de CHAÎNE, sans la
#: moindre E/S — le parseur en a besoin pour lire ``refConsultation`` dans une
#: URL de détail. Elle est déclarée ici plutôt que retirée de la liste
#: ci-dessous, pour que ``import urllib`` nu (qui, lui, ouvre
#: ``urllib.request`` par la bande) reste interdit.
RESEAU_TOLERE = ('urllib.parse',)

#: Interdits dans les modules PURS.
RESEAU_INTERDIT = (
    'httpx', 'requests', 'aiohttp', 'urllib.request', 'urllib.error',
    'urllib', 'http', 'socket', 'ftplib', 'smtplib', 'telnetlib', 'ssl',
    'webbrowser', 'xmlrpc',
)

#: Interdits dans les modules PURS : toute E/S disque.
DISQUE_INTERDIT = ('pathlib', 'shutil', 'tempfile', 'sqlite3', 'fileinput',
                   'glob', 'subprocess')

#: Les seuls attributs d'``os`` tolérés dans un module pur : lire un drapeau
#: d'environnement (l'interrupteur d'arrêt, VAO19) n'est pas une E/S disque.
OS_AUTORISE = frozenset({'environ', 'getenv', 'name'})


def _prefixe_interdit(nom, interdits):
    """``True`` si ``nom`` est un module interdit, ou un sous-module d'un tel.

    On compare par SEGMENTS (``a.b`` couvre ``a.b.c`` mais jamais ``a.bc``) —
    une comparaison par ``startswith`` nu bannirait ``httpx_stub`` ou
    ``socketserver`` par accident et rendrait la garde bruyante.
    """
    for interdit in interdits:
        if nom == interdit or nom.startswith(interdit + '.'):
            return True
    return False


def analyser_source(source, nom_module, reseau_autorise=False):
    """Les violations du contrat de pureté dans une source Python.

    Rend une liste de phrases françaises (vide = conforme). C'est une analyse
    STATIQUE : elle ne charge pas le module, donc elle reste valable même
    quand ``beautifulsoup4`` n'est pas installé sur la machine.
    """
    violations = []
    arbre = ast.parse(source, filename=nom_module)

    for noeud in ast.walk(arbre):
        # ── les imports, sous leurs deux formes
        noms = []
        if isinstance(noeud, ast.Import):
            noms = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:  # import relatif : ``from . import x``
                for alias in noeud.names:
                    cible = f'{noeud.module}.{alias.name}' if noeud.module else alias.name
                    if cible.split('.')[0] in SUPPORT_DE_TEST:
                        violations.append(
                            f'{nom_module}:{noeud.lineno} importe le chargeur de '
                            f'fixtures ({cible}) : un module de collecte ne lit '
                            'jamais un fichier de test.')
                continue
            noms = [noeud.module or '']

        for nom in noms:
            if _prefixe_interdit(nom, CADRES_INTERDITS):
                violations.append(
                    f'{nom_module}:{noeud.lineno} importe « {nom} » : le paquet '
                    'portail doit rester testable sans Django ni base.')
            tolere = _prefixe_interdit(nom, RESEAU_TOLERE)
            if (not reseau_autorise and not tolere
                    and _prefixe_interdit(nom, RESEAU_INTERDIT)):
                violations.append(
                    f'{nom_module}:{noeud.lineno} importe « {nom} » : seuls '
                    f'{", ".join(sorted(MODULES_RESEAU))} ont le droit de parler '
                    'au réseau.')
            if not reseau_autorise and _prefixe_interdit(nom, DISQUE_INTERDIT):
                violations.append(
                    f'{nom_module}:{noeud.lineno} importe « {nom} » : un module '
                    'pur ne touche pas au disque.')

        # ── ``open(...)`` en dur
        if isinstance(noeud, ast.Call) and not reseau_autorise:
            fonction = noeud.func
            if isinstance(fonction, ast.Name) and fonction.id == 'open':
                violations.append(
                    f'{nom_module}:{noeud.lineno} appelle open() : un module pur '
                    'reçoit du texte, il ne va pas le chercher.')
            if (isinstance(fonction, ast.Attribute)
                    and isinstance(fonction.value, ast.Name)
                    and fonction.value.id == 'os'
                    and fonction.attr not in OS_AUTORISE):
                violations.append(
                    f'{nom_module}:{noeud.lineno} appelle os.{fonction.attr}() : '
                    "seul l'accès à l'environnement est toléré dans un module pur.")

    return violations


def _modules_du_paquet():
    """(chemin, réseau_autorisé) pour chaque module Python du paquet.

    L'énumération est DYNAMIQUE : un module ajouté demain est couvert sans que
    personne n'ait à penser à l'inscrire quelque part.
    """
    for chemin in sorted(PAQUET.rglob('*.py')):
        relatif = chemin.relative_to(PAQUET)
        if relatif.parts[0] in SUPPORT_DE_TEST:
            continue
        yield chemin, (chemin.name in MODULES_RESEAU)


class GardeReseau:
    """Interdit toute ouverture de socket dans son bloc — et le PROUVE.

    Réutilisée par les tests des tâches suivantes : c'est la preuve
    d'exécution qui complète l'analyse statique (un module peut être pur à la
    lecture et appeler du réseau par une dépendance).
    """

    def __init__(self):
        self._vrai_socket = None

    def __enter__(self):
        self._vrai_socket = socket.socket

        def refus(*args, **kwargs):
            raise AssertionError(
                'Appel réseau interdit : les tests du collecteur portail ne '
                'parlent QU\'aux fixtures committées (règle #5 — la collecte '
                'réelle attend l\'accord fondateur, VAO4).')

        socket.socket = refus
        return self

    def __exit__(self, *exc):
        socket.socket = self._vrai_socket
        return False


class ContratDePureteTests(SimpleTestCase):
    """Le contrat de VAO15, appliqué à l'arbre réel du paquet."""

    def test_le_paquet_existe_avec_son_contrat(self):
        self.assertTrue(PAQUET.is_dir(), PAQUET)
        self.assertTrue((PAQUET / '__init__.py').is_file())
        self.assertTrue(issubclass(ErreurPortail, RuntimeError))

    def test_aucun_module_ne_viole_le_contrat(self):
        violations = []
        for chemin, reseau_autorise in _modules_du_paquet():
            source = chemin.read_text(encoding='utf-8')
            violations.extend(analyser_source(
                source, str(chemin.relative_to(PAQUET)), reseau_autorise))
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_les_modules_reseau_restent_l_exception(self):
        """Deux portes de sortie, pas trois : la liste est fermée."""
        reseau = [c.name for c, autorise in _modules_du_paquet() if autorise]
        self.assertLessEqual(set(reseau), set(MODULES_RESEAU))


class AnalyseurTests(SimpleTestCase):
    """L'analyseur est-il seulement CAPABLE de rougir ?

    Une garde qu'on ne teste pas à l'envers finit verte parce qu'elle
    n'inspecte plus rien. Chaque cas ci-dessous est une source fautive
    fabriquée ; l'analyseur doit la refuser.
    """

    def test_un_parseur_qui_importe_httpx_est_refuse(self):
        violations = analyser_source('import httpx\n', 'parser.py')
        self.assertTrue(violations)
        self.assertIn('httpx', violations[0])

    def test_un_parseur_qui_importe_django_est_refuse(self):
        violations = analyser_source(
            'from django.db import models\n', 'parser.py')
        self.assertTrue(violations)
        self.assertIn('Django', violations[0])

    def test_meme_le_client_ne_peut_pas_importer_django(self):
        violations = analyser_source(
            'from django.conf import settings\n', 'client.py',
            reseau_autorise=True)
        self.assertTrue(violations)

    def test_un_parseur_qui_importe_une_app_est_refuse(self):
        violations = analyser_source(
            'from apps.veille_ao.models import AvisMarche\n', 'parser.py')
        self.assertTrue(violations)

    def test_un_parseur_qui_ouvre_un_fichier_est_refuse(self):
        violations = analyser_source(
            "def lire():\n    return open('x.html').read()\n", 'parser.py')
        self.assertTrue(violations)
        self.assertIn('open()', violations[0])

    def test_un_parseur_qui_importe_pathlib_est_refuse(self):
        violations = analyser_source('from pathlib import Path\n', 'parser.py')
        self.assertTrue(violations)

    def test_un_module_de_collecte_ne_peut_pas_importer_les_fixtures(self):
        violations = analyser_source(
            'from .fixtures import charger\n', 'parser.py')
        self.assertTrue(violations)
        self.assertIn('fixtures', violations[0])

    def test_le_client_a_le_droit_au_reseau(self):
        self.assertEqual(
            analyser_source('import httpx\n', 'client.py', reseau_autorise=True),
            [])

    def test_urllib_parse_reste_autorise_dans_un_module_pur(self):
        """Analyser une chaîne d'URL n'est pas un appel réseau."""
        self.assertEqual(
            analyser_source('from urllib.parse import parse_qs\n', 'parser.py'),
            [])

    def test_urllib_nu_reste_interdit(self):
        """``import urllib`` ouvre ``urllib.request`` par la bande."""
        self.assertTrue(analyser_source('import urllib\n', 'parser.py'))

    def test_lire_l_environnement_reste_autorise(self):
        """L'interrupteur d'arrêt (VAO19) se lit dans l'environnement."""
        self.assertEqual(
            analyser_source(
                "import os\n\n\ndef arme():\n    return os.environ.get('X')\n",
                'garde_fous.py'),
            [])

    def test_ecrire_sur_le_disque_par_os_est_refuse(self):
        violations = analyser_source(
            "import os\n\n\ndef purger():\n    os.remove('x')\n",
            'garde_fous.py')
        self.assertTrue(violations)
        self.assertIn('os.remove', violations[0])


class FixturesCommitteesTests(SimpleTestCase):
    """Les fixtures sont là, lisibles, et DOCUMENTÉES pour ce qu'elles sont."""

    def test_les_sept_fixtures_sont_committees_et_lisibles(self):
        for nom in fixtures.TOUTES:
            with self.subTest(fixture=nom):
                contenu = fixtures.charger(nom)
                self.assertGreater(len(contenu), 500, nom)

    def test_les_cinq_cas_exiges_par_la_tache_sont_couverts(self):
        """10 lignes, réponse à 500, détail, erreur 403, page vide."""
        self.assertIn('nombreElement', fixtures.charger(fixtures.RESULTATS_10))
        self.assertIn('listePageSizeTop', fixtures.charger(fixtures.RESULTATS_500))
        self.assertIn('Caution provisoire', fixtures.charger(fixtures.DETAIL))
        self.assertIn('403', fixtures.charger(fixtures.ERREUR_403))
        self.assertIn('Aucun résultat', fixtures.charger(fixtures.RESULTATS_VIDE))

    def test_une_fixture_absente_le_dit_au_lieu_de_rendre_du_vide(self):
        with self.assertRaises(FileNotFoundError) as capture:
            fixtures.charger('fixture_qui_n_existe_pas.html')
        self.assertIn('fixture_qui_n_existe_pas.html', str(capture.exception))

    def test_la_provenance_est_ecrite_sans_detour(self):
        """Date de capture, URL d'origine, et la nature RECONSTRUITE assumée.

        Le contrat « chiffres vérifiés » du dépôt vaut aussi pour une fixture :
        présenter une reconstruction comme une capture réelle serait un
        mensonge de plus dans un fichier que personne ne relit.
        """
        readme = (fixtures.DOSSIER / 'README.md').read_text(encoding='utf-8')
        self.assertIn('2026-08-01', readme)
        self.assertIn('marchespublics.gov.ma', readme)
        self.assertIn('reconstruction', readme.lower())

    def test_chaque_fixture_porte_son_bandeau_de_provenance(self):
        for nom in fixtures.TOUTES:
            with self.subTest(fixture=nom):
                self.assertIn('FIXTURE RECONSTRUITE', fixtures.charger(nom))

    def test_charger_les_fixtures_n_ouvre_aucune_socket(self):
        with GardeReseau():
            for nom in fixtures.TOUTES:
                self.assertTrue(fixtures.charger(nom))

    def test_la_garde_reseau_rougit_bien_sur_un_appel_reseau(self):
        with GardeReseau():
            with self.assertRaises(AssertionError):
                socket.socket()
