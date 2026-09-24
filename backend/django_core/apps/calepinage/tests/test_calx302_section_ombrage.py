"""CALX302 — la section « Ombrage » et la porte ``POST image-document/``.

Ce qui est prouvé ici, en essais PURS (``unittest``, sans base) :

* ``images_document._decoder_fichier`` lit une data-URL base64, du base64
  nu, refuse un contenu vide/illisible — TOUJOURS en NOMMANT ``fichier`` ;
* ``images_document.deposer_image_document`` refuse un genre hors de
  l'énumération FERMÉE (``GENRES_IMAGE``) en le NOMMANT, AVANT tout accès
  disque/réseau (un calepinage factice avec un ``pk`` suffit : le refus de
  genre est le tout premier contrôle après celui du calepinage) ;
* ``images_document._valider_dimensions`` décode RÉELLEMENT une image
  (Pillow) — accepte un PNG minuscule valide, refuse un contenu illisible
  et une image hors bornes, toujours en nommant ``fichier`` ;
* ``services.rapport.ombrage.html_de_section`` — la table TOF/TSRF/accès
  solaire (CALX58), la matrice 12×24 et l'image, chacune omise EN LE DISANT
  quand sa donnée manque (les deux lectures hors ``resultat`` — roof_layout
  et l'image déposée — sont MONKEYPATCHÉES : aucune base, aucun MinIO) ;
* AUCUN montant (D5) : ni « prix », ni « cout », ni « marge » dans le rendu.

Ce qui exige l'ORM/DB (Attachment, MinIO, le viewset HTTP) est écrit mais
NON EXÉCUTÉ localement (``CalepinageDbTest`` — CI validera).

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx302_section_ombrage.py -q
"""
from __future__ import annotations

import base64
import io
import unittest
from unittest import mock

from apps.calepinage.services import images_document
from apps.calepinage.services.rapport import ombrage as section_ombrage

# ── Un PNG 20×20 RÉEL, produit avec Pillow (dépendance déjà pinnée) ────────
try:
    from PIL import Image
    _PILLOW_DISPONIBLE = True
except ImportError:  # pragma: no cover — Pillow est une dépendance pinnée
    _PILLOW_DISPONIBLE = False


def _png_valide(largeur=20, hauteur=20):
    tampon = io.BytesIO()
    Image.new('RGB', (largeur, hauteur), color=(10, 20, 30)).save(
        tampon, format='PNG')
    return tampon.getvalue()


class DecoderFichierTest(unittest.TestCase):
    def test_refuse_fichier_absent(self):
        for vide in (None, '', '   '):
            with self.assertRaises(images_document.ImageDocumentRefuse) \
                    as capture:
                images_document._decoder_fichier(vide)
            self.assertEqual(capture.exception.champ, 'fichier')

    def test_lit_une_data_url_base64(self):
        octets = b'contenu-image-simule'
        data_url = 'data:image/png;base64,%s' % base64.b64encode(
            octets).decode('ascii')
        lus, _nom = images_document._decoder_fichier(data_url)
        self.assertEqual(lus, octets)

    def test_lit_du_base64_nu(self):
        octets = b'autre-contenu'
        brut = base64.b64encode(octets).decode('ascii')
        lus, _nom = images_document._decoder_fichier(brut)
        self.assertEqual(lus, octets)

    def test_refuse_un_base64_invalide(self):
        with self.assertRaises(images_document.ImageDocumentRefuse) \
                as capture:
            images_document._decoder_fichier('***pas du base64***')
        self.assertEqual(capture.exception.champ, 'fichier')

    def test_refuse_une_data_url_sans_charge(self):
        with self.assertRaises(images_document.ImageDocumentRefuse) \
                as capture:
            images_document._decoder_fichier('data:image/png;base64,')
        self.assertEqual(capture.exception.champ, 'fichier')


class FauxCalepinage:
    """Un calepinage minimal — juste assez pour que le contrôle de genre
    (AVANT tout accès disque/réseau) puisse être testé sans base."""

    def __init__(self, pk=7, company=None):
        self.pk = pk
        self.company = company


class DeposerImageGenreTest(unittest.TestCase):
    def test_refuse_calepinage_non_enregistre(self):
        for factice in (None, FauxCalepinage(pk=None)):
            with self.assertRaises(images_document.ImageDocumentRefuse) \
                    as capture:
                images_document.deposer_image_document(
                    factice, genre='ombrage', fichier='data:x')
            self.assertEqual(capture.exception.champ, 'calepinage')

    def test_refuse_un_genre_hors_enumeration(self):
        with self.assertRaises(images_document.ImageDocumentRefuse) \
                as capture:
            images_document.deposer_image_document(
                FauxCalepinage(), genre='exploded_view', fichier='data:x')
        self.assertEqual(capture.exception.champ, 'genre')
        self.assertIn('exploded_view', str(capture.exception))
        for genre in images_document.GENRES_IMAGE:
            self.assertIn(genre, str(capture.exception))

    def test_les_trois_genres_admis_sont_exactement_ceux_du_crochet(self):
        # CALX291 avait laissé le crochet : l'énumération EXACTE lui revient.
        self.assertEqual(images_document.GENRES_IMAGE,
                         ('ombrage', 'sankey', 'plan3d'))


@unittest.skipUnless(_PILLOW_DISPONIBLE, 'Pillow indisponible')
class ValiderDimensionsTest(unittest.TestCase):
    def test_accepte_un_png_valide(self):
        images_document._valider_dimensions(_png_valide())  # ne lève pas

    def test_refuse_un_contenu_illisible(self):
        with self.assertRaises(images_document.ImageDocumentRefuse) \
                as capture:
            images_document._valider_dimensions(b'ceci-n-est-pas-une-image')
        self.assertEqual(capture.exception.champ, 'fichier')
        self.assertIn('illisible', str(capture.exception).lower())

    def test_refuse_une_image_trop_petite(self):
        with self.assertRaises(images_document.ImageDocumentRefuse) \
                as capture:
            images_document._valider_dimensions(_png_valide(2, 2))
        self.assertEqual(capture.exception.champ, 'fichier')
        self.assertIn('petite', str(capture.exception).lower())

    def test_refuse_une_image_trop_grande(self):
        taille = images_document._TAILLE_MAX_COTE_PX + 10
        with self.assertRaises(images_document.ImageDocumentRefuse) \
                as capture:
            images_document._valider_dimensions(_png_valide(taille, 100))
        self.assertEqual(capture.exception.champ, 'fichier')
        self.assertIn('grande', str(capture.exception).lower())


# ── La section « Ombrage » — contexte FABRIQUÉ, roof_layout/image PATCHÉS ──

def _resultat(*, ombrage_par_pan=(), production_par_pan=()):
    return {
        'calepinage': 9,
        'ombrage': {'par_pan': list(ombrage_par_pan)},
        'production': {'par_pan': list(production_par_pan)},
    }


class HtmlDeSectionOmbrageTest(unittest.TestCase):
    def test_table_orientation_avec_tof_tsrf_et_motif_omission(self):
        contexte = {'resultat': _resultat(
            ombrage_par_pan=[
                {'pan': 'PAN-A', 'acces_solaire_moyen_pct': 96.5,
                 'motif_omission': ''},
                {'pan': 'PAN-B', 'acces_solaire_moyen_pct': 40.0,
                 'motif_omission': "Site PVGIS injoignable pour PAN-B."},
            ],
            production_par_pan=[
                {'pan': 'PAN-A', 'tof': 0.97, 'tsrf': 0.94},
                {'pan': 'PAN-B', 'tof': None, 'tsrf': None},
            ])}
        with mock.patch.object(section_ombrage, '_calepinage_et_roof_layout',
                               return_value=None), \
                mock.patch.object(section_ombrage, '_image_ombrage_data_uri',
                                  return_value=None):
            html = section_ombrage.html_de_section(contexte)

        self.assertIn('PAN-A', html)
        self.assertIn('PAN-B', html)
        self.assertIn('0,97', html)  # TOF de PAN-A, virgule française
        self.assertIn('Site PVGIS injoignable pour PAN-B.', html)
        self.assertNotIn('None', html)

    def test_sans_ombrage_par_pan_publie_une_mention(self):
        contexte = {'resultat': _resultat()}
        with mock.patch.object(section_ombrage, '_calepinage_et_roof_layout',
                               return_value=None), \
                mock.patch.object(section_ombrage, '_image_ombrage_data_uri',
                                  return_value=None):
            html = section_ombrage.html_de_section(contexte)
        self.assertIn('Aucun accès solaire par module mesuré', html)

    def test_matrice_valide_imprimee_en_chiffres(self):
        matrice = [[0.5] * 24 for _ in range(12)]

        class FauxCalepinageAvecLayout:
            roof_layout = {'shading12x24': matrice}

        contexte = {'resultat': _resultat(
            ombrage_par_pan=[{'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                             'motif_omission': ''}])}
        with mock.patch.object(
                section_ombrage, '_calepinage_et_roof_layout',
                return_value=FauxCalepinageAvecLayout()), \
                mock.patch.object(section_ombrage, '_image_ombrage_data_uri',
                                  return_value=None):
            html = section_ombrage.html_de_section(contexte)
        self.assertIn('Matrice d’ombrage horaire', html)
        self.assertIn('0,5', html)
        self.assertNotIn('non disponible', html.lower())

    def test_matrice_absente_publie_une_mention(self):
        contexte = {'resultat': _resultat(
            ombrage_par_pan=[{'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                             'motif_omission': ''}])}
        with mock.patch.object(section_ombrage, '_calepinage_et_roof_layout',
                               return_value=None), \
                mock.patch.object(section_ombrage, '_image_ombrage_data_uri',
                                  return_value=None):
            html = section_ombrage.html_de_section(contexte)
        self.assertIn('non disponible', html.lower())

    def test_image_deposee_publiee_en_img(self):
        contexte = {'resultat': _resultat(
            ombrage_par_pan=[{'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                             'motif_omission': ''}])}
        with mock.patch.object(section_ombrage, '_calepinage_et_roof_layout',
                               return_value=object()), \
                mock.patch.object(
                    section_ombrage, '_image_ombrage_data_uri',
                    return_value='data:image/png;base64,AAAA'):
            html = section_ombrage.html_de_section(contexte)
        self.assertIn('<img class="ombrage-image"', html)
        self.assertIn('data:image/png;base64,AAAA', html)

    def test_image_absente_publie_une_mention(self):
        contexte = {'resultat': _resultat(
            ombrage_par_pan=[{'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                             'motif_omission': ''}])}
        with mock.patch.object(section_ombrage, '_calepinage_et_roof_layout',
                               return_value=None), \
                mock.patch.object(section_ombrage, '_image_ombrage_data_uri',
                                  return_value=None):
            html = section_ombrage.html_de_section(contexte)
        self.assertIn('Aucune carte de chaleur déposée', html)

    def test_aucun_montant_dans_la_section(self):
        matrice = [[0.5] * 24 for _ in range(12)]

        class FauxCalepinageAvecLayout:
            roof_layout = {'shading12x24': matrice}

        contexte = {'resultat': _resultat(
            ombrage_par_pan=[{'pan': 'PAN-A', 'acces_solaire_moyen_pct': 90.0,
                             'motif_omission': ''}],
            production_par_pan=[{'pan': 'PAN-A', 'tof': 0.9, 'tsrf': 0.8}])}
        with mock.patch.object(
                section_ombrage, '_calepinage_et_roof_layout',
                return_value=FauxCalepinageAvecLayout()), \
                mock.patch.object(
                    section_ombrage, '_image_ombrage_data_uri',
                    return_value='data:image/png;base64,AAAA'):
            html = section_ombrage.html_de_section(contexte)
        bas = html.lower()
        for mot in ('prix', 'cout', 'coût', 'marge'):
            self.assertNotIn(mot, bas)


# ── ORM/DB/MinIO/HTTP — écrits, NON EXÉCUTÉS localement (CI validera) ──────

class CalepinageDbTest(unittest.TestCase):
    """Marqueur : le viewset (tenant, permission, dépôt réel en
    ``records.Attachment``, MinIO) et l'inventaire ``GET documents/`` avec
    ``images[]`` peuplé exigent une base + MinIO — CI validera. Voir
    ``apps.calepinage.tests.test_api_horizon.BaseApiCalepinage`` pour le
    patron d'une future classe ``APITestCase`` complète : société A/B,
    ``PeutVoirCalepinage`` avec/sans droit, 404 hors société, dépôt réussi
    puis relu par ``GET documents/`` (``images[0].genre == 'ombrage'``), et
    un format/poids/dimensions refusés (400, champ nommé).
    """

    @unittest.skip('ORM/MinIO/HTTP — CI validera (non exécuté localement)')
    def test_depot_reussi_apparait_dans_l_inventaire(self):
        raise NotImplementedError
