"""ASEC24 (C-ASEC-008, volet lecteur) — le moteur de proposition refuse toute
clé de toit hors du préfixe de la société du devis (``roofs/<company_id>/``)
AVANT de la télécharger ; la page se rend alors sans toit.

La clé étrangère est posée directement en base (l'API d'écriture est fermée
par ASEC22). Le téléchargement MinIO est observé (doublure ``wraps`` absente
ici : on vérifie qu'il n'est PAS appelé pour la clé étrangère et qu'il l'est
pour la clé légitime).

Test-du-test : retirer le contrôle de préfixe ⇒
``test_cle_etrangere_non_telechargee`` échoue.
"""
from unittest import mock

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine import builder
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


class ToitPrefixeSocieteTests(TestCase):
    def setUp(self):
        self.societe_a = make_company(slug='asec24-a', nom='ASEC24 A')
        self.societe_b = make_company(slug='asec24-b', nom='ASEC24 B')
        self.user = make_user(self.societe_a)
        self.devis = make_devis(
            self.societe_a, self.user, make_client(self.societe_a),
            [('Onduleur hybride', '1', '12000')], reference='DEV-ASEC24-1')

    def _poser(self, cle):
        Devis.objects.filter(pk=self.devis.pk).update(roof_image=cle)
        self.devis.refresh_from_db()

    def test_cle_etrangere_non_telechargee(self):
        self._poser('roofs/%s/DEV-B.png' % self.societe_b.pk)
        with mock.patch('apps.ventes.utils.pdf.download_roof_image',
                        return_value=PNG) as telecharger, \
                self.assertLogs('apps.ventes', level='WARNING') as journal:
            uri = builder._roof_render_data_uri(self.devis)
        self.assertEqual(uri, '')
        telecharger.assert_not_called()
        texte = '\n'.join(journal.output)
        self.assertIn('ASEC24', texte)
        self.assertNotIn('DEV-B.png', texte)

    def test_cle_societe_rendue(self):
        self._poser('roofs/%s/DEV-ASEC24-1.png' % self.societe_a.pk)
        with mock.patch('apps.ventes.utils.pdf.download_roof_image',
                        return_value=PNG) as telecharger:
            uri = builder._roof_render_data_uri(self.devis)
        telecharger.assert_called_once()
        self.assertTrue(uri.startswith('data:image/png;base64,'))

    def test_prefixe_strict(self):
        for cle in ('roofs/%s/../%s/x.png' % (self.societe_a.pk,
                                              self.societe_b.pk),
                    'autre/%s/x.png' % self.societe_a.pk,
                    'roofs/%s0/x.png' % self.societe_a.pk):
            with self.subTest(cle=cle):
                self.assertFalse(builder.cle_toit_de_la_societe(self.devis, cle))
        self.assertTrue(builder.cle_toit_de_la_societe(
            self.devis, 'roofs/%s/x.png' % self.societe_a.pk))
