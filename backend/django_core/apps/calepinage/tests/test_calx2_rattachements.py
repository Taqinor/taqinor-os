"""CALX2 — les actions rattachées résolvent À L'IDENTIQUE après le
déménagement.

CE QUE CE TEST PROTÈGE
----------------------
Avant CALX2, les dix imports qui RATTACHENT une ``@action`` au
``CalepinageViewSet`` vivaient dans ``apps/calepinage/urls.py``. Toute tâche
qui ajoutait une action devait donc déclarer ``urls.py`` dans son ``Files:``,
et ``scripts/plan_lanes.py`` unionnait ces tâches dans UNE lane (mesuré sur le
groupe CALX : 13 des 16 fusions de lanes venaient de là). CALX2 les déplace
dans ``views/rattachements.py``, surface APPEND-ONLY (décision D-CALX 13).

Un déménagement d'imports est exactement le genre de changement qui « marche »
jusqu'au jour où une action n'est plus découverte par le routeur : DRF lit les
attributs de la CLASSE au moment de ``router.register``
(``get_extra_actions``), donc un import qui s'exécuterait APRÈS le register
ne routerait rien — et la route disparaîtrait en silence, sans qu'aucun test
d'API ne le dise autrement
que par un 404. Ce test fige donc les TREIZE chemins, un par un, en dur.

Aucune base de données : ``SimpleTestCase``, lecture d'URLconf et de source.

Run :
    python manage.py test apps.calepinage.tests.test_calx2_rattachements -v2
"""
import ast
import pathlib
import re

from django.test import SimpleTestCase
from django.urls import reverse

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
SOURCE_URLS = (RACINE_APP / 'urls.py').read_text(encoding='utf-8')
SOURCE_RATTACHEMENTS = (
    RACINE_APP / 'views' / 'rattachements.py').read_text(encoding='utf-8')

#: LES TREIZE ACTIONS RATTACHÉES, avec le chemin qu'elles servaient AVANT
#: CALX2 et qu'elles doivent servir à l'octet près APRÈS. Le nom de route est
#: ``calepinage-<nom de fonction avec les « _ » en « - »>`` (DRF :
#: ``func.url_name = func.__name__.replace('_', '-')`` quand ``url_name`` n'est
#: pas donné, et ``SimpleRouter`` le rend en ``{basename}-{url_name}``).
#: ``reverse()`` sans préfixe rend TOUJOURS le chemin interne canonique
#: ``/api/django/…`` (le second montage ``/api/v1/…`` est sous namespace).
ROUTES_ATTENDUES = (
    # (nom de route, arguments, chemin exact)
    ('calepinage-equipements', ('1',),
     '/api/django/calepinage/calepinages/1/equipements/'),
    ('calepinage-horizon', ('1',),
     '/api/django/calepinage/calepinages/1/horizon/'),
    # CALX7 — `export-csv` (url_name) est le tableur CSV de `SortiesMixin`
    # (`url_path='export.csv'`) ; l'export de simulation, renommé
    # `export_csv_simulation`, garde `url_path='export-csv'`.
    ('calepinage-export-csv', ('1',),
     '/api/django/calepinage/calepinages/1/export.csv/'),
    ('calepinage-export-csv-simulation', ('1',),
     '/api/django/calepinage/calepinages/1/export-csv/'),
    ('calepinage-modeles', (),
     '/api/django/calepinage/calepinages/modeles/'),
    ('calepinage-deverrouiller', ('1',),
     '/api/django/calepinage/calepinages/1/deverrouiller/'),
    ('calepinage-archiver', ('1',),
     '/api/django/calepinage/calepinages/1/archiver/'),
    ('calepinage-restaurer-corbeille', ('1',),
     '/api/django/calepinage/calepinages/1/restaurer-corbeille/'),
    ('calepinage-export-layout', ('1',),
     '/api/django/calepinage/calepinages/1/export-layout/'),
    ('calepinage-import-layout', ('1',),
     '/api/django/calepinage/calepinages/1/import-layout/'),
    ('calepinage-pompage', ('1',),
     '/api/django/calepinage/calepinages/1/pompage/'),
    ('calepinage-pertes', ('1',),
     '/api/django/calepinage/calepinages/1/pertes/'),
    ('calepinage-enregistrer-pertes', ('1',),
     '/api/django/calepinage/calepinages/1/enregistrer-pertes/'),
    ('calepinage-dossiers-reglementaires', ('1',),
     '/api/django/calepinage/calepinages/1/dossiers-reglementaires/'),
)

#: Les méthodes HTTP de chaque action, figées elles aussi : un
#: ``methods=['get']`` devenu ``['post']`` change le contrat sans changer
#: l'URL.
METHODES_ATTENDUES = {
    'equipements': {'get'},
    'horizon': {'get'},
    'export_csv': {'get'},
    'modeles': {'get'},
    'deverrouiller': {'post'},
    'archiver': {'post'},
    'restaurer_corbeille': {'post'},
    'export_layout': {'get'},
    'import_layout': {'post'},
    'pompage': {'post'},
    'pertes': {'get'},
    'enregistrer_pertes': {'post'},
    'dossiers_reglementaires': {'get'},
}


class RoutesRattacheesInchangeesTest(SimpleTestCase):
    """Les treize chemins sont servis EXACTEMENT comme avant CALX2."""

    def test_chaque_action_resout_au_meme_chemin(self):
        for nom, args, attendu in ROUTES_ATTENDUES:
            with self.subTest(route=nom):
                self.assertEqual(
                    reverse(nom, args=args), attendu,
                    f"La route « {nom} » ne résout plus vers {attendu}. "
                    "Le déplacement des imports de rattachement d'urls.py "
                    "vers views/rattachements.py (CALX2) doit être INVISIBLE "
                    "côté HTTP : ni url_path ni url_name ne changent.")

    def test_les_treize_actions_sont_decouvertes_par_le_routeur(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        attachees = {a.__name__ for a in CalepinageViewSet.get_extra_actions()}
        manquantes = sorted(set(METHODES_ATTENDUES) - attachees)
        self.assertEqual(
            manquantes, [],
            f"Action(s) plus rattachée(s) au viewset : {manquantes}. "
            "L'import de views/rattachements.py doit s'exécuter AVANT "
            "router.register (DRF inspecte la classe à cet instant).")

    def test_les_methodes_http_sont_inchangees(self):
        from apps.calepinage.views.calepinages import CalepinageViewSet

        par_nom = {a.__name__: a
                   for a in CalepinageViewSet.get_extra_actions()}
        for nom, methodes in METHODES_ATTENDUES.items():
            with self.subTest(action=nom):
                self.assertIn(nom, par_nom)
                self.assertEqual(set(par_nom[nom].mapping), methodes)


class UrlsPyNEstPlusSurLeCheminDesTachesTest(SimpleTestCase):
    """``urls.py`` importe UN seul module de rattachement, avant le
    register."""

    def test_un_seul_import_de_rattachement(self):
        imports = re.findall(r'^from \.views import (\w+)', SOURCE_URLS,
                             flags=re.MULTILINE)
        self.assertEqual(
            imports, ['rattachements'],
            "urls.py ne doit importer QUE `rattachements` depuis .views "
            "(CALX2 / D-CALX 13) : chaque import d'action supplémentaire ici "
            "remet urls.py dans le `Files:` de toutes les tâches du groupe, "
            "et plan_lanes refond le groupe en une seule lane.")

    def test_le_rattachement_precede_le_register(self):
        position_import = SOURCE_URLS.find(
            'from .views import rattachements')
        position_register = SOURCE_URLS.find('router.register(')
        self.assertNotEqual(position_import, -1,
                            "urls.py n'importe plus views/rattachements.py.")
        self.assertNotEqual(position_register, -1,
                            "urls.py n'appelle plus router.register.")
        self.assertLess(
            position_import, position_register,
            "L'import de views/rattachements.py doit précéder "
            "router.register : DRF découvre les @action en inspectant la "
            "classe AU MOMENT du register (get_extra_actions).")


class RattachementsEstUneListeAppendOnlyTest(SimpleTestCase):
    """Le fichier ne porte QUE des imports — rien qui puisse se réordonner."""

    def _arbre(self):
        return ast.parse(SOURCE_RATTACHEMENTS)

    def test_aucune_logique_dans_le_fichier(self):
        interdits = []
        for noeud in self._arbre().body:
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(noeud, ast.Assign):
                continue
            if isinstance(noeud, ast.Expr) and isinstance(noeud.value,
                                                          ast.Constant):
                continue  # la docstring du module
            interdits.append(type(noeud).__name__)
        self.assertEqual(
            interdits, [],
            f"views/rattachements.py porte de la logique ({interdits}). "
            "C'est une LISTE : une ligne d'import par action, ajoutée en fin, "
            "jamais de vue, jamais de path(), jamais de router.")

    def test_la_liste_documentee_reflete_les_imports_dans_l_ordre(self):
        from apps.calepinage.views import rattachements

        importes = []
        for noeud in self._arbre().body:
            if isinstance(noeud, ast.ImportFrom) and noeud.level == 1:
                importes.extend(alias.name for alias in noeud.names)
        self.assertEqual(
            importes, list(rattachements.MODULES_RATTACHES),
            "MODULES_RATTACHES ne reflète plus les imports du fichier, ou "
            "l'ordre a été remanié. La règle append-only est stricte : on "
            "AJOUTE en fin, on ne trie jamais (deux tâches qui trient ce "
            "fichier chacune à leur façon, c'est le conflit garanti).")

    def test_aucun_couplage_ao_ni_ged(self):
        """D-CALX 2 — le module calepinage n'importe ni ``ao`` ni ``ged``."""
        for interdit in ('apps.ao', 'apps.ged', 'from apps import ao',
                         'from apps import ged'):
            self.assertNotIn(
                interdit, SOURCE_RATTACHEMENTS,
                f"« {interdit} » dans views/rattachements.py : aucune tâche "
                "CALX n'ajoute un couplage AO/GED (décision D-CALX 2).")
