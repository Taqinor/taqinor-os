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
import base64
import io
from unittest import mock

import fitz
from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine import artefacts_rendu, builder
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_cj2b_graphe_mensuel import bloc_horaire

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
PNG_VALIDE = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ'
    '/pLvAAAAAElFTkSuQmCC')


#: Devis résidentiel COMPLET (deux onduleurs + batterie réelle, 14 × 550 Wc =
#: 7,70 kWc — mêmes lignes que test_cj2b_graphe_mensuel) : le moteur résidentiel
#: refuse tout document sans couche économique (« missing quote field »).
LIGNES_RESIDENTIEL = [
    ('Onduleur réseau 10kW', '1', '11700'),
    ('Onduleur hybride 5kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]


class ToitPrefixeSocieteTests(TestCase):
    def setUp(self):
        self.societe_a = make_company(slug='asec24-a', nom='ASEC24 A')
        self.societe_b = make_company(slug='asec24-b', nom='ASEC24 B')
        self.user = make_user(self.societe_a)
        self.devis = make_devis(
            self.societe_a, self.user, make_client(self.societe_a),
            LIGNES_RESIDENTIEL, reference='DEV-ASEC24-1',
            etude_params={**DEUX_OPTIONS,
                          'etude_horaire': bloc_horaire(7.70)})

    def _poser(self, cle):
        Devis.objects.filter(pk=self.devis.pk).update(roof_image=cle)
        self.devis.refresh_from_db()

    def test_cle_etrangere_non_telechargee(self):
        self._poser('roofs/%s/DEV-B.png' % self.societe_b.pk)
        with mock.patch('apps.ventes.utils.pdf.download_roof_image',
                        return_value=PNG) as telecharger, \
                self.assertLogs('apps.ventes', level='WARNING') as journal:
            uri = artefacts_rendu._roof_render_data_uri(self.devis)
        self.assertEqual(uri, '')
        telecharger.assert_not_called()
        texte = '\n'.join(journal.output)
        self.assertIn('ASEC24', texte)
        self.assertNotIn('DEV-B.png', texte)

    def test_cle_societe_rendue(self):
        self._poser('roofs/%s/DEV-ASEC24-1.png' % self.societe_a.pk)
        with mock.patch('apps.ventes.utils.pdf.download_roof_image',
                        return_value=PNG) as telecharger:
            uri = artefacts_rendu._roof_render_data_uri(self.devis)
        telecharger.assert_called_once()
        self.assertTrue(uri.startswith('data:image/png;base64,'))

    def test_prefixe_strict(self):
        for cle in ('roofs/%s/../%s/x.png' % (self.societe_a.pk,
                                              self.societe_b.pk),
                    'autre/%s/x.png' % self.societe_a.pk,
                    'roofs/%s0/x.png' % self.societe_a.pk):
            with self.subTest(cle=cle):
                self.assertFalse(
                    artefacts_rendu.cle_toit_de_la_societe(self.devis, cle))
        self.assertTrue(artefacts_rendu.cle_toit_de_la_societe(
            self.devis, 'roofs/%s/x.png' % self.societe_a.pk))

    def test_photo_de_toiture_sans_piece_jointe_vide(self):
        """SPL167 — cas direct du lecteur de photo (le golden le neutralise) :
        aucune pièce jointe image ⇒ '' par le chemin NORMAL, sans passer par
        le repli d'erreur (qui journaliserait un avertissement)."""
        with self.assertNoLogs('apps.ventes', level='WARNING'):
            self.assertEqual(
                artefacts_rendu._roof_photo_data_uri(self.devis), '')

    def test_nombre_de_pages_inchange(self):
        """CLIENT — toit légitime : même nombre de pages que sans toit ;
        vrai ``download_roof_image``, seul ``utils.pdf.get_minio_client``
        est remplacé (comme ``test_pdf_public_accepte_signe``)."""
        from apps.ventes.quote_engine.residential import renderer
        cle = 'roofs/%s/DEV-ASEC24-1.png' % self.societe_a.pk
        client = mock.Mock()
        client.get_object.return_value = {'Body': io.BytesIO(PNG_VALIDE)}

        def pages(devis):
            renderer._PDF_CACHE.clear()
            data = builder.build_quote_data(devis, {'_embed_roof_render': True})
            pdf = renderer.render_pdf_bytes(builder.echapper_textes_client(data))
            with fitz.open(stream=pdf, filetype='pdf') as doc:
                return data, len(doc)
        _, temoin = pages(self.devis)
        self._poser(cle)
        with mock.patch('apps.ventes.utils.pdf.get_minio_client',
                        return_value=client):
            data, n = pages(self.devis)
        client.get_object.assert_called_once()
        self.assertEqual(client.get_object.call_args.kwargs['Key'], cle)
        self.assertTrue(data['roof_render'].startswith('data:image/png'))
        self.assertEqual(n, temoin)
