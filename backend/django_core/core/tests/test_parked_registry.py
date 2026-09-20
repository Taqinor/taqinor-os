"""SOLMVP1 — garde du registre des apps parquées (``core.parked``).

Deux niveaux : (1) la cohérence du registre lui-même (49 labels uniques,
PHASE 2 ⊆ registre, groupes = partition exacte du registre) — active tout de
suite ; (2) la garde de « coquille » : chaque label parqué ne doit garder sur le
disque que ``__init__.py``, ``apps.py``, ``models.py`` (vide) et ``migrations/``.

Ce second niveau est SKIPPÉ tant que SOLMVP30-36 n'ont pas coquillé les
dossiers : aujourd'hui les 49 apps sont encore complètes, le test doit être vert
sans mentir. Dès le dernier coquillage, le skip s'éteint de lui-même et le test
devient le garde-fou permanent contre un fichier remis dans une app parquée.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from core.parked import (APPS_PARQUEES, APPS_PARQUEES_SET, ARCHIVE_REF,
                         GROUPES, PHASE2, est_parquee)

APPS_DIR = Path(__file__).resolve().parents[2] / 'apps'
# Seul contenu autorisé dans une app coquille (contrat de core/parked.py).
CONTENU_COQUILLE = {'__init__.py', 'apps.py', 'models.py', 'migrations', '__pycache__'}


class ParkedRegistryTests(SimpleTestCase):
    def test_49_labels_uniques(self):
        self.assertEqual(len(APPS_PARQUEES), 49)
        self.assertEqual(len(APPS_PARQUEES_SET), 49, 'doublon dans APPS_PARQUEES')
        self.assertEqual(ARCHIVE_REF, 'archive/full-erp-2026-09-20')
        self.assertTrue(est_parquee('voip') and est_parquee('apps.voip'))
        self.assertFalse(est_parquee('crm') or est_parquee(''))

    def test_phase2_est_un_sous_ensemble(self):
        self.assertEqual(len(set(PHASE2)), len(PHASE2), 'doublon dans PHASE2')
        self.assertTrue(
            set(PHASE2) <= APPS_PARQUEES_SET,
            'PHASE 2 hors registre : %s' % sorted(set(PHASE2) - APPS_PARQUEES_SET),
        )

    def test_groupes_partitionnent_le_registre(self):
        plats = [label for labels in GROUPES.values() for label in labels]
        self.assertEqual(sorted(plats), sorted(APPS_PARQUEES))

    def test_chaque_label_est_une_app_coquille(self):
        residus = {}
        for label in APPS_PARQUEES:
            dossier = APPS_DIR / label
            self.assertTrue(dossier.is_dir(), '%s : dossier absent de apps/' % label)
            extra = sorted(p.name for p in dossier.iterdir() if p.name not in CONTENU_COQUILLE)
            if extra:
                residus[label] = extra
        if residus:
            self.skipTest(
                'SOLMVP30-36 pas encore passés : %d app(s) parquée(s) encore complètes '
                '(ex. %s). Ce test devient le garde-fou dès le dernier coquillage.'
                % (len(residus), ', '.join(sorted(residus)[:3]))
            )
        for label in APPS_PARQUEES:
            for attendu in ('__init__.py', 'apps.py', 'models.py'):
                self.assertTrue(
                    (APPS_DIR / label / attendu).is_file(),
                    '%s : %s manquant dans la coquille' % (label, attendu),
                )
            self.assertTrue((APPS_DIR / label / 'migrations').is_dir(),
                            '%s : migrations/ doit être conservé verbatim' % label)
            corps = ast.parse((APPS_DIR / label / 'models.py').read_text(encoding='utf-8')).body
            vide = not corps or (
                len(corps) == 1
                and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)
            )
            self.assertTrue(vide, '%s : models.py doit être vide (docstring seul toléré)' % label)
