"""Runner de tests du PROJET (``settings.TEST_RUNNER``).

Un seul rôle aujourd'hui : rendre la purge de fin de ``TransactionTestCase``
compatible avec les **coquilles de migrations** du MVP solaire.

Le problème, une fois pour tout le dépôt
----------------------------------------
Les 47 apps sorties du périmètre (``core.parked``, recette complète dans
``docs/parked-modules.md``) ont perdu leurs MODÈLES — une migration
``SeparateDatabaseAndState`` retire l'ÉTAT Django — mais gardent leurs TABLES :
la base de test est bâtie par les migrations GELÉES, donc ces tables sont là,
avec leurs clés étrangères vers les tables CONSERVÉES (par exemple
``mrp_ordrefabrication`` → ``installations_ordreassemblage``,
et beaucoup vers ``authentication_company``).

Or ``TransactionTestCase._fixture_teardown()`` appelle ``flush``, qui ne tronque
que les tables des modèles INSTALLÉS. Postgres refuse alors le ``TRUNCATE``
(« cannot truncate a table referenced in a foreign key constraint … use
TRUNCATE … CASCADE »), la purge échoue, les tables restent pleines et le test
SUIVANT de la classe explose en doublon de clé — une cascade d'ERROR sans aucun
rapport avec le code testé (constatée sur les 7 classes
``TransactionTestCase`` du dépôt qui ne déclarent pas ``available_apps``).

Le correctif est CENTRAL et unique : ce runner emballe
``TransactionTestCase._fixture_teardown`` pour que tout ``flush`` émis pendant
la purge passe en ``CASCADE`` (``core.test_utils.cascading_flush``) et que le
``statement_timeout`` de production ne l'annule pas
(``core.test_utils.wide_fixture_teardown_timeout``). Cascader est le
comportement CORRECT : les tables des coquilles sont VIDES en test (plus aucun
modèle ne peut y écrire), et c'est littéralement ce que Django fait déjà quand
une classe déclare ``available_apps`` (``allow_cascade=self.available_apps is
not None``) — d'où le fait que la seule classe verte avant ce correctif était
justement celle qui borne ses apps (``apps/crm/tests_webhook.py``).

Rien d'autre n'est modifié : ``DiscoverRunner`` garde tout son comportement
(découverte, ``--parallel``, ``--keepdb``, shards CI).

Portée : la rustine est posée sur la CLASSE Django au moment du
``setup_test_environment()`` du runner, donc elle couvre le processus principal
et les workers ``--parallel`` obtenus par ``fork`` (Linux — l'image de test et
la CI). Sous une méthode de démarrage ``spawn``, Django ré-initialise ses
workers sans repasser par le runner du projet : les classes portant
``WideTeardownTimeoutMixin`` restent alors couvertes pour le timeout, et le
``CASCADE`` suit le chemin standard de Django. Aucun test du dépôt ne tourne sur
ce chemin (l'unique harnais local est le même conteneur Linux).
"""
from __future__ import annotations

import functools

from django.test import TransactionTestCase
from django.test.runner import DiscoverRunner

from core.test_utils import cascading_flush, wide_fixture_teardown_timeout

#: Marqueur d'idempotence : la rustine ne doit pas s'empiler si
#: ``setup_test_environment()`` est appelé deux fois (runner imbriqué, outil
#: tiers qui réutilise la classe).
_ATTR_POSEE = '_taqinor_flush_cascade'


def installer_flush_cascade():
    """Pose (une seule fois) la purge « CASCADE + timeout large » sur
    ``TransactionTestCase``. Idempotent, sans effet hors tests."""
    origine = TransactionTestCase._fixture_teardown
    if getattr(origine, _ATTR_POSEE, False):
        return

    @functools.wraps(origine)
    def _fixture_teardown(self):  # noqa: N802 — nom imposé par Django
        aliases = self._databases_names(include_mirrors=False)
        with wide_fixture_teardown_timeout(aliases), cascading_flush(aliases):
            origine(self)

    setattr(_fixture_teardown, _ATTR_POSEE, True)
    TransactionTestCase._fixture_teardown = _fixture_teardown


class TaqinorTestRunner(DiscoverRunner):
    """``DiscoverRunner`` + purge de fixtures compatible coquilles parquées."""

    def setup_test_environment(self, **kwargs):
        installer_flush_cascade()
        super().setup_test_environment(**kwargs)
