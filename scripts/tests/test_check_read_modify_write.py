"""Tests YDATA16 — scripts/check_read_modify_write.py.

Pure stdlib (unittest), no Django — mirrors the DB-free checker. Run:
    python -m unittest scripts.tests.test_check_read_modify_write -v
"""
import ast
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_read_modify_write as crmw  # noqa: E402 — après sys.path/setup() (D-ENF22)


def _findings(src):
    """ATST43 — le VRAI ``check_file`` sur la source écrite (cible RMW seule)."""
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "services.py"
        f.write_text(src, encoding="utf-8")
        return [t for t in crmw.check_file(f) if not t[1].endswith(".statut")]


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


class MainSurArbreFautifTests(unittest.TestCase):
    """ATST43 (C-ATST-022) — ``main()`` joué sur un arbre factice : mutants
    « ``if offenders:`` → ``if False:`` » ou balayage vidé ⇒ rouge."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.svc = base / "apps" / "demo" / "services.py"
        self.svc.parent.mkdir(parents=True)
        self.allow = base / "allow.txt"
        for nom in ("APPS_DIR", "CORE_DIR", "AUTH_DIR", "ALLOWLIST_PATH"):
            self.addCleanup(setattr, crmw, nom, getattr(crmw, nom))
        crmw.APPS_DIR, crmw.CORE_DIR = base / "apps", base / "core"
        crmw.AUTH_DIR, crmw.ALLOWLIST_PATH = base / "authentication", self.allow

    def _main(self, src):
        self.svc.write_text(src, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            return crmw.main([]), out.getvalue()

    def test_services_fautif_rend_un(self):
        code, out = self._main(BARE_RMW)
        self.assertEqual(code, 1, out)
        self.assertIn("apps/demo/services.py::incr", out)

    def test_allowlist_ou_verrou_rend_zero(self):
        self.allow.write_text(f"{crmw._rel(self.svc)}::incr\n", encoding="utf-8")
        self.assertEqual(self._main(BARE_RMW)[0], 0)
        self.allow.unlink()
        self.assertEqual(self._main(LOCKED_SELECT_FOR_UPDATE)[0], 0)


def _tous(src):
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "views.py"
        f.write_text(src, encoding="utf-8")
        return crmw.check_file(f)


class TestAnglesMortsHorsServices(unittest.TestCase):
    """ACNC50 — un test par angle mort ; le même motif sous select_for_update est sain."""

    VERROU = "    Doc.objects.select_for_update().get(pk=1)\n"

    def _sain_sous_verrou(self, src):
        tete, corps = src.split("\n", 1)
        verrouille = f"{tete}\n{self.VERROU}{corps}"
        ast.parse(verrouille)  # jamais vert par une SyntaxError avalée
        self.assertEqual(_tous(verrouille), [])

    def test_vue_hors_services_est_balayee(self):
        tmp = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        vue = base / "apps" / "facturation" / "views" / "facture.py"
        vue.parent.mkdir(parents=True)
        vue.write_text("def perform_destroy(self, instance):\n"
                       "    if instance.statut != 'brouillon':\n        raise Exception('x')\n"
                       "    instance.delete()\n", encoding="utf-8")
        for nom in ("APPS_DIR", "CORE_DIR", "AUTH_DIR", "ALLOWLIST_PATH"):
            self.addCleanup(setattr, crmw, nom, getattr(crmw, nom))
        crmw.APPS_DIR, crmw.CORE_DIR = base / "apps", base / "core"
        crmw.AUTH_DIR, crmw.ALLOWLIST_PATH = base / "authentication", base / "allow.txt"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = crmw.main([])
        self.assertEqual(code, 1, out.getvalue())
        self.assertIn("views/facture.py::perform_destroy (instance.statut)", out.getvalue())

    def test_garde_en_return(self):
        src = ("def rendre(pret):\n    if pret.statut == 'rendu':\n        return pret\n"
               "    pret.statut = 'rendu'\n    pret.save()\n")
        self.assertIn(("rendre", "pret.statut"), _tous(src))
        self._sain_sous_verrou(src)

    def test_drapeau_d_etat(self):
        src = ("def mouvementer(liv):\n    if liv.stock_mouvemente:\n        raise Exception('x')\n"
               "    Mouvement.objects.create(livraison=liv)\n")
        self.assertIn(("mouvementer", "liv.stock_mouvemente"), _tous(src))
        self._sain_sous_verrou(src)

    def test_calcul_par_variable_locale(self):
        src = ("def sortir(produit, n):\n    qte = produit.quantite - n\n"
               "    produit.quantite = qte\n    produit.save()\n")
        self.assertIn(("sortir", "produit.quantite"), _tous(src))
        src2 = ("def sortir(produit, n):\n    qte = produit.quantite - n\n"
                "    Produit.objects.filter(pk=produit.pk).update(quantite=qte)\n")
        self.assertIn(("sortir", "produit.quantite via variable"), _tous(src2))
        self._sain_sous_verrou(src)

    def test_save_complet_apres_lecture_du_statut(self):
        src = ("def perform_update(self, serializer):\n"
               "    if serializer.instance.statut == 'valide':\n        notifier()\n"
               "    serializer.save()\n")
        self.assertIn(("perform_update", "serializer.instance.statut save complet"), _tous(src))
        self.assertEqual(_tous(src.replace("serializer.save()", "serializer.save(update_fields=['x'])")), [])
        self._sain_sous_verrou(src)


if __name__ == "__main__":
    unittest.main()
