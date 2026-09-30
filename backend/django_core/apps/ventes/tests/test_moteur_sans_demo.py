"""QJR629 — le moteur PDF n'embarque plus de devis démo.

``generate_devis_premium.py`` portait un QUOTE_INPUT (nom, adresse et téléphone
RÉELS du fondateur) et une seconde formule de prix par blocs exécutée À
L'IMPORT pour initialiser ses globales ; plus un ``generate()`` de script, un
bloc ``__main__`` et trois helpers morts. Tout cela est supprimé : les globales
ont des défauts INERTES et chaque rendu passe par ``apply_quote_data``.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_moteur_sans_demo -v 2
"""
import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine import figures, pricing
from apps.ventes.quote_engine import generate_devis_premium as moteur

#: Racine ``backend/django_core`` (``services/simulator`` garde sa propre copie).
_RACINE = Path(__file__).resolve().parents[3]
#: Téléphone du fondateur tel qu'il figurait dans l'ancien QUOTE_INPUT —
#: découpé pour que ce fichier de test ne le contienne pas lui-même.
_TEL_FONDATEUR = "0661" + "850410"


class TestMoteurSansDemo(SimpleTestCase):
    def test_plus_de_devis_demo_ni_de_formule_par_blocs(self):
        for nom in ("QUOTE_INPUT", "calculate_quote", "_Q", "generate",
                    "logo_badge_p1"):
            with self.subTest(nom=nom):
                self.assertFalse(hasattr(moteur, nom), nom)

    def test_helpers_morts_supprimes(self):
        self.assertFalse(hasattr(figures, "tolerance_de"))
        self.assertFalse(hasattr(pricing, "annual_bill_from_kwh"))

    def test_le_telephone_du_fondateur_n_est_plus_dans_le_code(self):
        fautifs = []
        for p in _RACINE.rglob("*"):
            if (not p.is_file() or "__pycache__" in p.parts
                    or p.suffix not in (".py", ".json", ".html", ".txt",
                                        ".yml", ".yaml", ".md")):
                continue
            try:
                if _TEL_FONDATEUR in p.read_text(encoding="utf-8",
                                                 errors="ignore"):
                    fautifs.append(str(p.relative_to(_RACINE)))
            except OSError:
                continue
        self.assertEqual(fautifs, [])

    def test_defauts_inertes_a_l_import(self):
        """Un chargement NEUF du module (sans aucun rendu) ne porte aucune
        donnée client ; les dérivées de module restent importables."""
        spec = importlib.util.spec_from_file_location(
            "apps.ventes.quote_engine._moteur_neuf_qjr629", moteur.__file__)
        neuf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(neuf)
        self.assertEqual(neuf.CLIENT_NAME, "")
        self.assertEqual(neuf.CLIENT_ADDR, "")
        self.assertEqual(neuf.CLIENT_PHONE, "")
        self.assertEqual(neuf.REF, "")
        self.assertEqual(neuf.TOTAL_SANS, 0)
        self.assertEqual(neuf.TOTAL_AVEC, 0)
        self.assertEqual(neuf.SANS_ITEMS, [])
        self.assertEqual(neuf.AVEC_ITEMS, [])
        self.assertEqual(len(neuf.YEARS), 26)
        self.assertEqual(len(neuf.CUMUL_S), 26)
        self.assertEqual(len(neuf.CUMUL_A), 26)

    def test_un_devis_residentiel_se_rend_sans_erreur(self):
        from apps.ventes.tests import _moteur_fixtures as F

        html = moteur.render_html_for(F.donnees_legacy())
        self.assertIn("</html>", html.lower())
        self.assertNotIn(_TEL_FONDATEUR, html)
