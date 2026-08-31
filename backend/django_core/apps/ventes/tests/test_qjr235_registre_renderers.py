# -*- coding: utf-8 -*-
"""QJR235 — la sélection de renderer est un REGISTRE, et son repli est NOMMÉ.

TEST ROUGE D'ABORD : ``quote_engine/builder`` choisissait son renderer par
QUATRE blocs ``if`` copiés-collés, sans registre. Un cinquième marché dont le
bloc était oublié dégradait **silencieusement** vers le moteur legacy, sans le
journal de repli nommé que le code promet pourtant ailleurs (le
``except Unsupported`` agricole, lui, journalise bien — QJR17(d)).

AUCUN CHANGEMENT DE DOCUMENT RENDU : l'ordre du registre est celui des quatre
blocs, mot pour mot, et les empreintes de rendu existantes
(``test_quote_engine_formats``) restent vertes.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr235_registre_renderers -v 2
"""
import inspect
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import builder as B


class LeRegistreEstLaSeuleListe(SimpleTestCase):

    def test_l_ordre_du_registre_est_celui_des_blocs(self):
        """L'ordre des anciens blocs, moins l'entrée agricole que QJR236
        (décision DV1) a supprimée avec son renderer injoignable."""
        marches = [marche for marche, _mod, _pred in B.registre_renderers()]
        self.assertEqual(marches, ['industriel', 'commercial', 'residentiel'])
        self.assertNotIn('agricole', marches)

    def test_chaque_entree_porte_un_renderer_et_son_predicat(self):
        for marche, module, predicat in B.registre_renderers():
            with self.subTest(marche=marche):
                self.assertTrue(callable(predicat))
                self.assertTrue(hasattr(module, 'render_pdf_bytes'))
                self.assertTrue(hasattr(module, 'Unsupported'))

    def test_plus_aucun_if_is_de_dispatch_dans_le_builder(self):
        """Le grep, exécuté : le registre est la SEULE liste."""
        source = inspect.getsource(B.generate_premium_devis_pdf)
        for interdit in ('is_agricultural(', 'is_industrial(',
                         'is_commercial(', 'is_residential('):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, source)

    def test_les_quatre_blocs_copies_colles_ont_disparu(self):
        """Le patron dupliqué (``except <module>.Unsupported`` PAR MARCHÉ)
        n'existe plus — il ne reste que la capture GÉNÉRIQUE de la boucle du
        registre (``_renderer`` est sa variable de boucle, pas un module)."""
        source = inspect.getsource(B.generate_premium_devis_pdf)
        copies = re.findall(r'except\s+\w+\.Unsupported', source)
        self.assertEqual(copies, ['except _renderer.Unsupported'], copies)


class LeRepliEstNomme(SimpleTestCase):
    """Un repli n'est JAMAIS silencieux : marché, raison, devis."""

    def test_le_journal_nomme_les_trois_faits(self):
        with self.assertLogs(B.logger, level='WARNING') as journal:
            B._journaliser_repli('industriel', 'le renderer refuse ce devis',
                                 'DEV-202608-0042')
        message = '\n'.join(journal.output)
        self.assertIn('industriel', message)
        self.assertIn('DEV-202608-0042', message)
        self.assertIn('le renderer refuse ce devis', message)

    def test_un_marche_absent_du_registre_est_journalise(self):
        """LE ROUGE : ce cas-là ne produisait AUCUNE trace."""
        with self.assertLogs(B.logger, level='INFO') as journal:
            B._journaliser_repli(
                'vertical_inconnu',
                'aucune entrée du registre ne sert ce marché dans ce format',
                'DEV-202608-0043', niveau=B.logger.info)
        message = '\n'.join(journal.output)
        self.assertIn('vertical_inconnu', message)
        self.assertIn('aucune entrée du registre', message)

    def test_le_marche_du_devis_est_lu_sans_verdict(self):
        class _Devis:
            mode_installation = 'agricole'

        self.assertEqual(B._marche_du_devis(_Devis()), 'agricole')

    def test_un_devis_sans_marche_est_nomme_quand_meme(self):
        class _Devis:
            mode_installation = None

        self.assertIn('résidentiel', B._marche_du_devis(_Devis()))

    def test_le_dispatch_journalise_le_cas_sans_entree(self):
        """Le SITE d'appel, pas seulement l'aide : le dispatch appelle bien le
        journal quand aucune entrée n'a servi."""
        source = inspect.getsource(B.generate_premium_devis_pdf)
        self.assertIn('_servi_par is None', source)
        self.assertIn('_journaliser_repli(', source)
