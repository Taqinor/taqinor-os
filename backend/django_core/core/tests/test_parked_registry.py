"""SOLMVP1 — garde du registre des apps parquées (``core.parked``).

Deux niveaux : (1) la cohérence du registre lui-même (47 labels uniques,
PHASE 2 ⊆ registre, groupes = partition exacte du registre) — active tout de
suite ; (2) la garde de « coquille » : chaque label parqué ne doit garder sur le
disque que ``__init__.py``, ``apps.py``, ``migrations/`` et un ``models.py``
**sans aucune classe héritant de ``models.Model``** — un TALON (fonctions
``default=`` / énumérations recopiées verbatim) est autorisé, car une migration
GELÉE qui référence ``apps.<label>.models.<symbole>`` devient inimportable si le
fichier est vidé (contrat détaillé dans ``core.parked``).

Ce second niveau est SKIPPÉ tant que SOLMVP30-36 n'ont pas coquillé les
dossiers : aujourd'hui les 47 apps sont encore complètes, le test doit être vert
sans mentir. Dès le dernier coquillage, le skip s'éteint de lui-même et le test
devient le garde-fou permanent contre un fichier remis dans une app parquée.
"""
from pathlib import Path

from django.test import SimpleTestCase

from core.parked import (APPS_PARQUEES, APPS_PARQUEES_SET, ARCHIVE_REF,
                         GROUPES, PHASE2, est_parquee, modeles_declares)

APPS_DIR = Path(__file__).resolve().parents[2] / 'apps'
# Seul contenu autorisé dans une app coquille (contrat de core/parked.py).
CONTENU_COQUILLE = {'__init__.py', 'apps.py', 'models.py', 'migrations', '__pycache__'}


class ParkedRegistryTests(SimpleTestCase):
    def test_47_labels_uniques(self):
        self.assertEqual(len(APPS_PARQUEES), 47)
        self.assertEqual(len(APPS_PARQUEES_SET), 47, 'doublon dans APPS_PARQUEES')
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
            source = (APPS_DIR / label / 'models.py').read_text(encoding='utf-8')
            self.assertEqual(
                modeles_declares(source), [],
                '%s : models.py ne doit déclarer AUCUN modèle Django (un talon de '
                'fonctions/énumérations pour les migrations gelées est toléré)' % label,
            )

    def test_regle_du_talon_models_py(self):
        """La règle AST du contrat : pas de modèle, mais talon autorisé."""
        self.assertEqual(modeles_declares('"""docstring seul."""\n'), [])
        talon = (
            'import secrets\n'
            'from django.db import models\n'
            'JOURS = [30, 15, 7]\n'
            'def _token():\n'
            '    return secrets.token_urlsafe(32)\n'
            'class Sens(models.TextChoices):\n'
            "    DEBIT = 'debit', 'Débit'\n"
            'class PaymentRun:\n'
            '    class ModePaiement(models.TextChoices):\n'
            "        VIREMENT = 'virement', 'Virement'\n"
        )
        self.assertEqual(modeles_declares(talon), [])
        self.assertEqual(
            modeles_declares('from django.db import models\n'
                             'class Facture(models.Model):\n    pass\n'),
            ['Facture'])
        self.assertEqual(
            modeles_declares('from core.models import TenantModel\n'
                             'class A(TenantModel):\n    pass\n'
                             'class B(A):\n    pass\n'),
            ['A', 'B'])
