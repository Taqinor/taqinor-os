"""APDF16 (C-APDF-007) — ``/proposal`` relaie ``include_note_calcul`` avec la
même convention que ``include_etude`` (``1``/``true`` = oui) : un devis
agricole sert l'annexe « Note de calcul » (AGR319) sur demande.

Vrai GET APIClient sur un devis agricole créé par le serveur (montage
AGR124) ; moteur RÉEL (enveloppé ``wraps`` pour lire les options reçues),
seul le stockage MinIO est doublé (upload en mémoire). Pages comptées par
PyMuPDF quand il est présent.

Test-du-test : retirer le relais ``include_note_calcul`` de la vue ⇒
``test_param_1_quatre_pages`` échoue.
"""
from unittest import mock

from django.test import tag

from apps.ventes import quote_engine
from apps.ventes.models import Devis
from apps.ventes.tests import test_agr124_devis_auto_agricole as agr124
from apps.ventes.tests.test_agr310_renderer_agricole import fitz


@tag('pdf')
class ProposalNoteCalculTests(agr124.DevisAutoAgricoleTests):

    def _devis_agricole(self):
        self._pompe('15000')
        rep = self._post(self._lead())
        self.assertEqual(rep.status_code, 201, rep.data)
        return Devis.objects.get(pk=rep.data['id'])

    def _proposal(self, devis, suffixe=''):
        captures = {}

        def _upload(pdf_bytes, key, *a, **k):
            captures[key] = pdf_bytes
            return key
        with mock.patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                mock.patch('apps.ventes.utils.pdf._upload_pdf',
                           side_effect=_upload), \
                mock.patch('apps.ventes.utils.pdf.download_pdf',
                           side_effect=lambda key: captures.get(key, b'')), \
                mock.patch.object(
                    quote_engine, 'generate_premium_devis_pdf',
                    wraps=quote_engine.generate_premium_devis_pdf) as moteur:
            resp = self.api.get('/api/django/ventes/devis/%s/proposal/%s'
                                % (devis.pk, suffixe))
        self.assertEqual(resp.status_code, 200)
        options = moteur.call_args.args[1]
        pages = None
        if fitz is not None:
            pages = fitz.open(stream=resp.content, filetype='pdf').page_count
        return options, pages

    def test_param_1_quatre_pages(self):
        options, pages = self._proposal(self._devis_agricole(),
                                        '?include_note_calcul=1')
        self.assertTrue(options['include_note_calcul'])
        if pages is not None:
            self.assertEqual(pages, 4)

    def test_param_true(self):
        options, pages = self._proposal(self._devis_agricole(),
                                        '?include_note_calcul=true')
        self.assertTrue(options['include_note_calcul'])
        if pages is not None:
            self.assertEqual(pages, 4)

    def test_sans_param_trois_pages(self):
        options, pages = self._proposal(self._devis_agricole())
        self.assertFalse(options['include_note_calcul'])
        if pages is not None:
            self.assertEqual(pages, 3)
