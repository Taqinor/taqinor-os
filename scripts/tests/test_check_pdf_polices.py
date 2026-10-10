"""APDF51 — tests de la garde scripts/check_pdf_polices.py (stdlib, arbre jetable)."""
import tempfile
import unittest
from pathlib import Path

from scripts import check_pdf_polices as g

DOCKERFILE = ('RUN apt-get install -y --no-install-recommends \\\n'
              '    libcairo2 \\\n    fonts-liberation \\\n    fonts-noto-core \\\n    pkg-config\n')


def _arbre(fichiers):
    tmp = tempfile.TemporaryDirectory()
    racine = Path(tmp.name)
    (racine / 'backend/django_core').mkdir(parents=True)
    (racine / g.DOCKERFILE).write_text(DOCKERFILE, encoding='utf-8')
    for nom, texte in fichiers.items():
        p = racine / 'backend/django_core' / nom
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte, encoding='utf-8')
    return tmp, racine


class CheckPdfPolicesTests(unittest.TestCase):
    def test_familles_derivees_du_dockerfile(self):
        self.assertEqual(g.familles_systeme(DOCKERFILE), ['DejaVu', 'Liberation', 'Noto'])

    def test_depot_vert(self):
        racine = Path(__file__).resolve().parent.parent.parent
        self.assertEqual(g.verifier(racine), [])

    def test_homonyme_rouge(self):
        tmp, racine = _arbre({
            'a/gabarit.html': "<style>\n@font-face{font-family:'Noto Sans Arabic';src:url(x)}</style>",
            'a/b.py': 'css = f\'@font-face{{font-family:"DejaVu Sans";}}\'',
            'a/ok.py': 'css = "@font-face{font-family:\'DM Sans\';}"',
        })
        with tmp:
            erreurs = g.verifier(racine)
        self.assertEqual(len(erreurs), 2)
        self.assertTrue(any('gabarit.html:2' in e and 'Noto Sans Arabic' in e for e in erreurs))
        self.assertTrue(any('b.py:1' in e for e in erreurs))

    def test_sans_font_face_vert(self):
        tmp, racine = _arbre({'x.html': 'body{font-family:"Noto Sans Arabic"}'})
        with tmp:
            self.assertEqual(g.verifier(racine), [])


if __name__ == '__main__':
    unittest.main()
