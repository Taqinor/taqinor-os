"""Tests YDATA16 — scripts/check_read_modify_write.py.

Pure stdlib (unittest), no Django — mirrors the DB-free checker. Run:
    python -m unittest scripts.tests.test_check_read_modify_write -v
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_read_modify_write as crmw  # noqa: E402


def _findings(src):
    """Parse a module source and run the file-level checker on its tree."""
    tree = ast.parse(src)
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if crmw._function_calls_select_for_update(node):
            continue
        for varname, attr in crmw._rmw_sites_in_function(node):
            if crmw._function_saves_var(node, varname):
                findings.append((node.name, f"{varname}.{attr}"))
    return findings


BARE_RMW = '''
def incr(pk):
    obj = Counter.objects.get(pk=pk)
    obj.quantite = obj.quantite - 5
    obj.save()
'''

BARE_AUGASSIGN = '''
def incr(pk):
    obj = Counter.objects.get(pk=pk)
    obj.points += 10
    obj.save()
'''

LOCKED_SELECT_FOR_UPDATE = '''
def incr(pk):
    obj = Counter.objects.select_for_update().get(pk=pk)
    obj.quantite = obj.quantite - 5
    obj.save()
'''

F_EXPRESSION = '''
def incr(pk):
    obj = Counter.objects.get(pk=pk)
    obj.quantite = F('quantite') - 5
    obj.save()
'''

STRING_CONCAT = '''
def note(pk):
    obj = Doc.objects.get(pk=pk)
    obj.note = obj.note + "\\nappended"
    obj.save()
'''

NO_SAVE = '''
def compute(pk):
    obj = Counter.objects.get(pk=pk)
    obj.quantite = obj.quantite - 5
    return obj.quantite
'''


class TestReadModifyWrite(unittest.TestCase):
    def test_bare_read_modify_write_detected(self):
        self.assertEqual(_findings(BARE_RMW), [("incr", "obj.quantite")])

    def test_bare_augassign_detected(self):
        self.assertEqual(_findings(BARE_AUGASSIGN), [("incr", "obj.points")])

    def test_select_for_update_is_safe(self):
        self.assertEqual(_findings(LOCKED_SELECT_FOR_UPDATE), [])

    def test_f_expression_is_safe(self):
        self.assertEqual(_findings(F_EXPRESSION), [])

    def test_string_concat_ignored(self):
        self.assertEqual(_findings(STRING_CONCAT), [])

    def test_no_save_ignored(self):
        self.assertEqual(_findings(NO_SAVE), [])


STATUT_HORS_VERROU = '''
def valider(retour):
    if retour.statut != 'brouillon':
        raise ValueError('deja valide')
    retour.statut = 'valide'
    retour.save()
'''

STATUT_VERROUILLE = '''
def valider(retour):
    with transaction.atomic():
        retour = Retour.objects.select_for_update().get(pk=retour.pk)
        if retour.statut != 'brouillon':
            raise ValueError('deja valide')
        retour.statut = 'valide'
        retour.save()
'''

STATUT_SANS_ECRITURE = '''
def verifier(retour):
    if retour.statut != 'brouillon':
        raise ValueError('deja valide')
    return True
'''

STATUT_HORS_PARAMETRE = '''
def valider(pk):
    retour = Retour.objects.get(pk=pk)
    if retour.statut != 'brouillon':
        raise ValueError('deja valide')
    retour.save()
'''


def _statut_findings(src):
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.extend(crmw._status_findings(node))
    return out


class TestStatutHorsVerrou(unittest.TestCase):
    def test_statut_hors_verrou_detecte(self):
        self.assertEqual(_statut_findings(STATUT_HORS_VERROU),
                         [("valider", "retour.statut")])

    def test_relecture_sous_verrou_acceptee(self):
        self.assertEqual(_statut_findings(STATUT_VERROUILLE), [])

    def test_sans_ecriture_ou_hors_parametre_accepte(self):
        self.assertEqual(_statut_findings(STATUT_SANS_ECRITURE), [])
        self.assertEqual(_statut_findings(STATUT_HORS_PARAMETRE), [])

    def test_check_file_remonte_le_statut(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "services.py"
            f.write_text(STATUT_HORS_VERROU, encoding="utf-8")
            self.assertIn(("valider", "retour.statut"), crmw.check_file(f))


if __name__ == "__main__":
    unittest.main()
