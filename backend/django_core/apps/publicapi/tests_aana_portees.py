"""AANA45 — garde du nettoyage du code mort / des résidus parqués (périmètre analyse).

Constat C-AANA-036 : des symboles sans aucun appelant vivant (grep exécuté,
hors ``backend/parked/**``) restaient montés ou exportés. Ce test garde que :

* le scope ``juridique:read`` (app juridique PARQUÉE, aucune vue publique ne le
  consomme) n'est plus proposé dans ``SCOPE_CHOICES`` / ``ALL_SCOPES`` ;
* les routes FastAPI ``/kb/redaction``, ``/projets/generer-plan`` et
  ``/chat/transcribe`` (zéro appelant) ne sont plus montées ;
* les sélecteurs ``offlinesync`` sans appelant et le suivi vide
  ``cibles_parquees`` / ``CIBLES_MODULE_PROPRIETAIRE`` ne reviennent pas.

Source réelle : on lit les vrais modules et les vrais fichiers source — rien
n'est mocké.

Run :
    python manage.py test apps.publicapi.tests_aana_portees -v2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from . import portees

_DJANGO = Path(__file__).resolve().parents[2]
_BACKEND = _DJANGO.parent


def _noms_definis(chemin):
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            noms.update(t.id for t in noeud.targets
                        if isinstance(t, ast.Name))
    return noms


class JuridiqueScopeRetireTests(SimpleTestCase):
    def test_juridique_absent(self):
        codes = [c for c, _ in portees.SCOPE_CHOICES]
        self.assertNotIn('juridique:read', codes)
        self.assertNotIn('juridique:read', portees.ALL_SCOPES)
        self.assertFalse(hasattr(portees, 'SCOPE_READ_JURIDIQUE'))

    def test_les_autres_portees_sont_intactes(self):
        # Retrait ciblé : les 16 autres portées restent, dans le même ordre.
        self.assertEqual(len(portees.SCOPE_CHOICES), 16)
        self.assertEqual(portees.ALL_SCOPES[0], 'read:leads')
        self.assertEqual(portees.ALL_SCOPES[-1], 'tickets:write')


class RoutesFastapiMortesRetireesTests(SimpleTestCase):
    def test_fichiers_endpoints_supprimes(self):
        base = _BACKEND / 'fastapi_ia' / 'app'
        for rel in ('api/endpoints/kb.py', 'api/endpoints/projets.py',
                    'api/endpoints/transcription.py',
                    'services/plan_taches_service.py'):
            self.assertFalse((base / rel).exists(), rel)

    def test_main_ne_monte_plus_ces_routeurs(self):
        source = (_BACKEND / 'fastapi_ia' / 'app' / 'main.py').read_text(
            encoding='utf-8')
        for motif in ('kb.router', 'projets.router', 'transcription.router',
                      '"/kb"', '"/projets"', '"/chat"'):
            self.assertNotIn(motif, source, motif)
        # La transcription vocale vivante (/sql-agent/transcribe) reste montée.
        self.assertIn('voice.router', source)


class SelecteursEtParqueMortsRetiresTests(SimpleTestCase):
    def test_selecteurs_offlinesync_sans_appelant(self):
        noms = _noms_definis(_DJANGO / 'apps' / 'offlinesync' / 'selectors.py')
        for mort in ('operation_scoped', 'compte_conflits_ouverts',
                     'compte_par_statut'):
            self.assertNotIn(mort, noms, mort)
        # Les deux sélecteurs vivants (utilisés par tests/handlers) restent.
        self.assertLessEqual({'operations_scoped', 'conflits_ouverts'}, noms)

    def test_suivi_parque_vide_de_dataimport_retire(self):
        noms = _noms_definis(_DJANGO / 'apps' / 'dataimport' / 'services.py')
        self.assertNotIn('cibles_parquees', noms)
        self.assertNotIn('CIBLES_MODULE_PROPRIETAIRE', noms)
        from apps.dataimport import services
        # Le set résolu des cibles reste exactement FIELD_MAPS ∪ registre.
        self.assertLessEqual(set(services.FIELD_MAPS), set(services.TARGETS))
