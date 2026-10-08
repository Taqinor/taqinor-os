"""APDF18 (C-APDF-003) — la langue RÉSOLUE entre dans la clé idempotente de
la tâche Celery (un rendu FR puis AR du même devis ne ressert pas le PDF FR),
et les chemins sans langue explicite (tâche, generer-pdf, envoi, lien public,
copie signée — tous via ``generate_premium_devis_pdf`` → ``build_quote_data``)
rendent le devis d'un client arabe en arabe (résolution du moteur, APDF7).

Moteur réel ; seule l'empreinte de CONTENU est figée dans le test de clé
(pour isoler la part « langue » de la signature — dite ici).

Test-du-test : retirer la langue de ``_render_signature`` ⇒
``test_cle_celery_distincte_par_langue`` échoue.
"""
import re
from unittest import mock

from django.test import TestCase

from apps.ventes import tasks
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

ARABE = re.compile(r'[؀-ۿ]')


class LangueCinqCheminsTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf18-co', nom='APDF18')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, [
                ('Panneau mono 550W', '12', '1100'),
                ('Onduleur réseau 5kW', '1', '11700'),
            ], reference='DEV-APDF18-1')

    def _client_langue(self, langue):
        type(self.client_obj).objects.filter(pk=self.client_obj.pk).update(
            langue_document=langue)

    def test_cle_celery_distincte_par_langue(self):
        with mock.patch.object(tasks, '_content_version',
                               return_value='contenu-fige'):
            fr = tasks._render_signature(self.devis.pk, {'pdf_mode': 'full'})
            self._client_langue('ar')
            ar = tasks._render_signature(self.devis.pk, {'pdf_mode': 'full'})
            explicite_fr = tasks._render_signature(
                self.devis.pk, {'pdf_mode': 'full', 'langue_sortie': 'fr'})
        self.assertNotEqual(fr, ar)
        self.assertEqual(fr, explicite_fr)

    def test_cinq_chemins_arabe(self):
        """Les options que passent les chemins sans langue explicite
        (tâche/generer-pdf : celles du corps ; envoi : pdf_mode + jeton ;
        lien public : jeton ; copie signée : vide) → document arabe."""
        self._client_langue('ar')
        self.devis.refresh_from_db()
        for options in ({}, {'pdf_mode': 'full'},
                        {'pdf_mode': 'onepage', 'share_token': 'x' * 40},
                        {'share_token': 'y' * 40}):
            with self.subTest(options=options):
                data = build_quote_data(self.devis, clean_pdf_options(options))
                self.assertEqual(data['langue_sortie'], 'ar')
                libelles = ' '.join(
                    str(v) for v in data['libelles_document'].values())
                self.assertGreaterEqual(len(ARABE.findall(libelles)), 100)
