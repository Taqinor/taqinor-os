"""APDF7 (C-APDF-003) — le moteur résout la langue de sortie depuis le client
(puis la société) quand ``langue_sortie`` est absente ; ``?langue=`` explicite
reste prioritaire. Les chemins qui ne passent aucune langue (envoi, lien
public, copie signée, Celery, generer-pdf) rendent donc le devis d'un client
arabe en arabe.

Moteur réel (``build_quote_data``), aucune doublure.

Test-du-test : retirer la résolution ajoutée dans ``build_quote_data`` ⇒
``test_options_vides_client_ar`` échoue.
"""
import re

from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

ARABE = re.compile(r'[؀-ۿ]')


class LangueResolueMoteurTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf7-co', nom='APDF7')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, [
                ('Panneau mono 550W', '12', '1100'),
                ('Onduleur réseau 5kW', '1', '11700'),
            ], reference='DEV-APDF7-1')

    def _client_langue(self, langue):
        type(self.client_obj).objects.filter(pk=self.client_obj.pk).update(
            langue_document=langue)
        self.devis.refresh_from_db()

    def _nb_arabe(self, data):
        return len(ARABE.findall(' '.join(
            str(v) for v in (data.get('libelles_document') or {}).values())))

    def test_options_vides_client_ar(self):
        self._client_langue('ar')
        for options in ({}, {'pdf_mode': 'full'}, {'pdf_mode': 'onepage'}):
            with self.subTest(options=options):
                data = build_quote_data(self.devis, clean_pdf_options(options))
                self.assertEqual(data['langue_sortie'], 'ar')
                self.assertGreaterEqual(self._nb_arabe(data), 100)

    def test_explicite_prioritaire(self):
        self._client_langue('ar')
        data = build_quote_data(
            self.devis, clean_pdf_options({'langue_sortie': 'fr'}))
        self.assertEqual(data['langue_sortie'], 'fr')
        self.assertEqual(self._nb_arabe(data), 0)

    def test_client_fr_inchange(self):
        data = build_quote_data(self.devis, clean_pdf_options({}))
        self.assertEqual(data['langue_sortie'], 'fr')
        self.assertEqual(self._nb_arabe(data), 0)
