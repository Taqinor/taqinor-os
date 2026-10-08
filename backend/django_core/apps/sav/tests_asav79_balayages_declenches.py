"""ASAV79 — garde de classe : chaque balayage SAV / monitoring est planifié
ET borné aux sociétés actives.

Pour chaque fonction ``scan_*`` (``apps/sav``) et ``balayage_*``
(``apps/monitoring``), tests et migrations exclus :
  * DÉCLENCHEUR — elle est elle-même une ``@shared_task`` dont le nom figure
    dans ``beat_schedule`` (``erp_agentique/celery.py``), ou une telle tâche
    l'appelle ;
  * BORNE SOCIÉTÉ — son corps appelle ``active_company_ids()`` (ou
    ``active_companies()``, la même source unique SCA19).
Un délégué d'une ligne (``from .tasks import scan_x``) n'est pas un balayage.
Une ``@shared_task`` qui appelle un autre balayage est un déclencheur, pas un
balayage. Liste d'exceptions VIDE. Lecture AST seule (aucune base).

Run :
    python manage.py test apps.sav.tests_asav79_balayages_declenches -v2
"""
import ast
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

DJANGO_CORE = Path(__file__).resolve().parents[2]
RACINES = (
    (DJANGO_CORE / 'apps' / 'sav', 'scan_'),
    (DJANGO_CORE / 'apps' / 'monitoring', 'balayage_'),
)
BEAT = DJANGO_CORE / 'erp_agentique' / 'celery.py'
BORNES = {'active_company_ids', 'active_companies'}

SANS_DECLENCHEUR = (
    "balayage sans déclencheur : aucune @shared_task du beat_schedule ne "
    "l'appelle (ajoutez la tâche ET son entrée beat)")
SANS_BORNE = (
    "balayage sans borne société : filtrez par active_company_ids() "
    "(un tenant suspendu ne doit plus être balayé)")


def taches_du_beat(fichier_beat):
    """Noms de tâches (``'task': '...'``) déclarés dans le beat_schedule."""
    noms = set()
    for noeud in ast.walk(ast.parse(Path(fichier_beat).read_text('utf-8'))):
        if isinstance(noeud, ast.Dict):
            for cle, valeur in zip(noeud.keys, noeud.values):
                if (isinstance(cle, ast.Constant) and cle.value == 'task'
                        and isinstance(valeur, ast.Constant)):
                    noms.add(valeur.value)
    return noms


def _nom_shared_task(fonction):
    for deco in fonction.decorator_list:
        if isinstance(deco, ast.Call):
            cible = deco.func
            nom = getattr(cible, 'id', None) or getattr(cible, 'attr', None)
            if nom == 'shared_task':
                for kw in deco.keywords:
                    if kw.arg == 'name' and isinstance(kw.value, ast.Constant):
                        return kw.value.value
                return fonction.name
        elif getattr(deco, 'id', None) == 'shared_task':
            return fonction.name
    return None


def _appels(fonction):
    noms = set()
    for noeud in ast.walk(fonction):
        if isinstance(noeud, ast.Call):
            cible = noeud.func
            noms.add(getattr(cible, 'id', None) or getattr(cible, 'attr', None))
    return noms


def _est_delegue(fonction):
    for noeud in ast.walk(fonction):
        if (isinstance(noeud, ast.ImportFrom)
                and (noeud.module or '').endswith('tasks')
                and any(a.name == fonction.name for a in noeud.names)):
            return True
    return False


def verifier(racines, fichier_beat):
    """Liste de messages ``fichier::fonction — motif``."""
    beat = taches_du_beat(fichier_beat)
    balayages, declencheurs = [], []
    for racine, prefixe in racines:
        for chemin in sorted(Path(racine).rglob('*.py')):
            rel = chemin.relative_to(racine)
            if ('migrations' in rel.parts or chemin.name.startswith('tests')
                    or chemin.name.startswith('test_')):
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for fonction in arbre.body:
                if not isinstance(fonction, ast.FunctionDef):
                    continue
                tache = _nom_shared_task(fonction)
                if tache in beat:
                    declencheurs.append(fonction)
                if not fonction.name.startswith(prefixe):
                    continue
                if _est_delegue(fonction):
                    continue
                balayages.append((f'{chemin.name}::{fonction.name}', fonction,
                                  tache, prefixe))
    noms_balayages = {f.name for _, f, _, _ in balayages}
    signalements = []
    for cle, fonction, tache, prefixe in balayages:
        appelle_balayage = bool(_appels(fonction) & (noms_balayages - {fonction.name}))
        if tache is not None and appelle_balayage:
            continue  # déclencheur d'un autre balayage, pas un balayage.
        planifie = tache in beat or any(
            fonction.name in _appels(d) for d in declencheurs)
        if not planifie:
            signalements.append(f'{cle} — {SANS_DECLENCHEUR}')
        if not (_appels(fonction) & BORNES):
            signalements.append(f'{cle} — {SANS_BORNE}')
    return signalements


class BalayagesDeclenchesTests(SimpleTestCase):

    def test_chaque_scan_planifie(self):
        manquants = [s for s in verifier(RACINES, BEAT)
                     if SANS_DECLENCHEUR in s]
        self.assertEqual(manquants, [], '\n'.join(manquants))

    def test_chaque_scan_borne(self):
        manquants = [s for s in verifier(RACINES, BEAT) if SANS_BORNE in s]
        self.assertEqual(manquants, [], '\n'.join(manquants))

    def test_fixture_signalee_deux_fois(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier) / 'sav'
            racine.mkdir()
            (racine / 'tasks.py').write_text(
                'def scan_test():\n'
                '    return Ticket.objects.all()\n', encoding='utf-8')
            beat = Path(dossier) / 'celery.py'
            beat.write_text("SCHEDULE = {'x': {'task': 'autre.tache'}}\n",
                            encoding='utf-8')
            signalements = verifier(((racine, 'scan_'),), beat)
        self.assertEqual(len(signalements), 2)
        self.assertTrue(any(SANS_DECLENCHEUR in s for s in signalements))
        self.assertTrue(any(SANS_BORNE in s for s in signalements))
        self.assertTrue(all(s.startswith('tasks.py::scan_test')
                            for s in signalements))
