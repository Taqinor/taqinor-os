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
        # contextvars (stdlib) : drapeau « règles d'origine » du rendu
        # (décision fondateur 08/10/2026, nouveaux rendus seulement) ;
        # contextlib (stdlib) : format anglais posé puis retiré (AMOT101).
        self.assertEqual(mods - {"decimal", "contextvars", "contextlib"},
                         set())


class TestReglesDuRenduReinitialisees(SimpleTestCase):
    """FIX-MOTEUR (audit Fable L3, #1130) — ``poser_regles_origine`` pose sans
    retirer : deux devis successifs dans le même thread (worker Celery,
    runserver), le second ne doit pas hériter des règles du premier."""

    def setUp(self):
        self.addCleanup(montants.poser_regles_origine, False)

    def _devis_envoye_rendu(self):
        montants.poser_regles_origine(False, avant_2710=True)
        self.assertTrue(montants.regles_avant_2710())

    def test_requete_suivante_repart_des_regles_courantes(self):
        from django.core.signals import request_started
        montants.poser_regles_origine(True)
        self.assertTrue(montants.regles_origine())
        request_started.send(sender=None)
        self.assertFalse(montants.regles_origine())
        self.assertFalse(montants.regles_avant_2710())

    def test_tache_celery_suivante_repart_des_regles_courantes(self):
        from types import SimpleNamespace

        from celery.signals import task_prerun
        self._devis_envoye_rendu()
        task_prerun.send(sender=None, task=SimpleNamespace(request=SimpleNamespace(is_eager=False)))
        self.assertFalse(montants.regles_avant_2710())
        # tâche exécutée en ligne DANS la requête : le rendu en cours garde ses règles
        self._devis_envoye_rendu()
        task_prerun.send(sender=None, task=SimpleNamespace(request=SimpleNamespace(is_eager=True)))
        self.assertTrue(montants.regles_avant_2710())
