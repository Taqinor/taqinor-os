"""QJR613 — un seul formateur monétaire au centime (ROUND_HALF_UP) pour le moteur.

``_fmt2`` / ``_fmt2_mad`` vivaient dans ``generate_devis_premium.py`` (qui
importe matplotlib au chargement) : les paquets premium résidentiel /
commercial / industriel ne pouvaient pas les réutiliser. Ils déménagent dans
``quote_engine/montants.py`` (stdlib seulement) ; le moteur legacy les
ré-exporte sous leurs anciens noms, rendu octet-identique.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_montants -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine import generate_devis_premium as moteur
from apps.ventes.quote_engine import montants

NNBSP = " "


class TestFormateurUnique(SimpleTestCase):
    def test_le_moteur_reexporte_le_formateur_partage(self):
        self.assertIs(moteur._fmt2, montants.fmt_centimes)
        self.assertIs(moteur._fmt2_mad, montants.fmt_centimes_mad)

    def test_montants_au_centime(self):
        self.assertEqual(montants.fmt_centimes(63187.50), f"63{NNBSP}187,50")
        self.assertEqual(montants.fmt_centimes(0.005), "0,01")
        self.assertEqual(montants.fmt_centimes(1200.80), f"1{NNBSP}200,80")

    def test_suffixe_mad(self):
        self.assertEqual(montants.fmt_centimes_mad(1200.80),
                         f"1{NNBSP}200,80 MAD")

    def test_valeur_illisible_rendue_telle_quelle(self):
        self.assertEqual(montants.fmt_centimes("abc"), "abc")
        self.assertEqual(montants.fmt_centimes(None), "None")

    def test_module_stdlib_seulement(self):
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(montants))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mods.add((node.module or "").split(".")[0])
        # AMOT26 — contextvars (stdlib) porte le drapeau « règles d'origine ».
        self.assertEqual(mods - {"decimal", "contextvars"}, set())
