"""CALX107 câblage — ``GET calepinages/<pk>/plan-importe/`` : URL et taille.

CE QUI EST PROUVÉ ICI
---------------------
1. **La route existe et elle est gardée** — ``plan-importe``, GET seul,
   ``PeutVoirCalepinage``, rattachée au ``CalepinageViewSet`` par le nom EXACT
   de sa fonction (DRF mappe par ``__name__``) et déclarée dans
   ``MODULES_RATTACHES``.
2. **Les dimensions sont LUES, jamais supposées** — ``dimensions_image`` rend
   les pixels naturels d'un PNG (bloc ``IHDR``) et d'un JPEG (segment ``SOF``),
   et ``(None, None)`` pour tout le reste : un fichier dont l'en-tête ne porte
   pas sa taille ne reçoit aucun gabarit de remplacement (D-CALX 7).
3. **Chaque refus NOMME son champ** — ``underlay``, ``kind``, ``attachmentId``
   (deux cas distincts), en français.
4. **Le contrat committé et la porte disent la même chose** — les huit clés de
   ``contract_samples/calepinage_plan_importe.json``, et le motif de son
   exemple « taille inconnue » est CELUI que la porte produit.

Les classes 1 à 4 sont des ``SimpleTestCase`` : aucune base, elles tournent
sur le poste de la lane. ``PlanImporteApiTest`` exige la base (pièce jointe +
magasin d'objets) et n'a PAS été exécutée ici.

Run :
    python manage.py test apps.calepinage.tests.test_calx107_plan_importe -v2
"""
from __future__ import annotations

import json
import pathlib
import struct

from django.test import SimpleTestCase, TestCase

from apps.calepinage.views.plan_importe import (
    FOND_PHOTO,
    MOTIF_FICHIER_ABSENT,
    PIECE_INTROUVABLE,
    SANS_FOND,
    SANS_PIECE,
    dimensions_image,
    motif_taille_inconnue,
)

RACINE = pathlib.Path(__file__).resolve().parent.parent
ECHANTILLON = RACINE / 'contract_samples' / 'calepinage_plan_importe.json'

#: Les huit clés servies par la porte — la forme est FIXE (aucune clé absente).
CLES_DU_CONTRAT = ('calepinage', 'attachment', 'filename', 'mime', 'url',
                   'largeur', 'hauteur', 'motif')


def _contrat():
    return json.loads(ECHANTILLON.read_text(encoding='utf-8'))


def _png(largeur, hauteur):
    """Un PNG d'ESSAI réduit à sa signature et à son bloc ``IHDR``.

    Assez pour la lecture de dimensions, qui ne regarde que l'en-tête : on ne
    fabrique pas une image réelle pour prouver la lecture d'un en-tête.
    """
    return (b'\x89PNG\r\n\x1a\n'
            + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', largeur, hauteur)
            + b'\x08\x06\x00\x00\x00')


def _jpeg(largeur, hauteur, *, marqueur=0xC0):
    """Un JPEG d'ESSAI : ``SOI``, un segment ``APP0``, puis un ``SOF``.

    Le segment ``APP0`` est là exprès : il oblige le lecteur à SAUTER un
    segment par sa longueur avant d'atteindre celui qui porte les
    dimensions — c'est la seule façon de prouver qu'il ne lit pas au hasard.
    """
    soi = b'\xff\xd8'
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00' + b'\x00' * 9
    sof = (bytes((0xFF, marqueur)) + struct.pack('>H', 17) + b'\x08'
           + struct.pack('>HH', hauteur, largeur) + b'\x03' + b'\x00' * 9)
    return soi + app0 + sof


class RoutagePlanImporteTest(SimpleTestCase):
    """Sans route, l'écran irait chercher le fichier du fond dans le vide."""

    def _actions(self):
        from apps.calepinage import urls  # noqa: F401
        from apps.calepinage.views.calepinages import CalepinageViewSet

        return CalepinageViewSet, {methode.__name__: methode
                                   for methode
                                   in CalepinageViewSet.get_extra_actions()}

    def test_l_action_est_enregistree_sur_le_pivot(self):
        _viewset, actions = self._actions()
        self.assertIn(
            'plan_importe', actions,
            "L'action « plan-importe » n'est pas rattachée au "
            'CalepinageViewSet — vérifier la ligne ajoutée en fin de '
            'views/rattachements.py (CALX107).')
        self.assertEqual(actions['plan_importe'].url_path, 'plan-importe')
        self.assertTrue(actions['plan_importe'].detail)
        self.assertEqual(set(actions['plan_importe'].mapping), {'get'})

    def test_le_nom_de_la_fonction_egale_le_nom_de_l_attribut(self):
        """DRF mappe par ``__name__`` — un alias serait ignoré (CALX7)."""
        viewset, _actions = self._actions()
        self.assertEqual(getattr(viewset, 'plan_importe').__name__,
                         'plan_importe')

    def test_la_porte_exige_le_droit_de_voir(self):
        _viewset, actions = self._actions()
        self.assertEqual(
            [garde.__name__ for garde
             in actions['plan_importe'].kwargs['permission_classes']],
            ['PeutVoirCalepinage'])

    def test_le_module_est_declare_dans_MODULES_RATTACHES(self):
        from apps.calepinage.views.rattachements import MODULES_RATTACHES

        self.assertIn('plan_importe', MODULES_RATTACHES)


class DimensionsImageTest(SimpleTestCase):
    """Les pixels sont LUS dans l'en-tête — ou inconnus, et on le dit."""

    def test_png_rend_ses_pixels_naturels(self):
        self.assertEqual(dimensions_image(_png(2480, 1754)), (2480, 1754))

    def test_jpeg_rend_ses_pixels_naturels(self):
        self.assertEqual(dimensions_image(_jpeg(1600, 900)), (1600, 900))

    def test_jpeg_progressif_est_lu_aussi(self):
        """``SOF2`` (progressif) porte ses dimensions comme ``SOF0``."""
        self.assertEqual(dimensions_image(_jpeg(800, 600, marqueur=0xC2)),
                         (800, 600))

    def test_un_marqueur_qui_n_est_pas_un_SOF_ne_donne_aucune_taille(self):
        """``\\xc4`` est une table de Huffman, pas un « Start Of Frame »."""
        self.assertEqual(dimensions_image(_jpeg(800, 600, marqueur=0xC4)),
                         (None, None))

    def test_un_format_sans_en_tete_lisible_ne_rend_aucune_taille(self):
        for contenu in (b'', None, b'0\n  0 SECTION\n', b'%PDF-1.7\n'):
            self.assertEqual(dimensions_image(contenu), (None, None))

    def test_un_png_tronque_ne_rend_aucune_taille(self):
        self.assertEqual(dimensions_image(_png(10, 10)[:14]), (None, None))

    def test_une_dimension_nulle_n_est_pas_une_dimension(self):
        """0 px n'est pas une taille : on préfère l'inconnu au zéro."""
        self.assertEqual(dimensions_image(_png(0, 100)), (None, None))


class RefusNommesTest(SimpleTestCase):
    """Un « non trouvé » générique est interdit : chaque refus nomme."""

    def test_les_quatre_motifs_sont_en_francais_et_distincts(self):
        motifs = (SANS_FOND, FOND_PHOTO, SANS_PIECE, PIECE_INTROUVABLE)
        self.assertEqual(len(set(motifs)), 4)
        for motif in motifs:
            self.assertTrue(motif.strip())
            self.assertNotIn('not found', motif.lower())

    def test_le_refus_photo_renvoie_vers_la_porte_des_photos(self):
        self.assertIn('photos/', FOND_PHOTO)

    def test_le_refus_sans_piece_nomme_le_champ_du_document(self):
        self.assertIn('attachmentId', SANS_PIECE)

    def test_le_motif_de_taille_inconnue_nomme_le_fichier(self):
        self.assertIn('plan.dxf', motif_taille_inconnue('plan.dxf'))

    def test_le_fichier_illisible_a_son_propre_motif(self):
        self.assertNotEqual(MOTIF_FICHIER_ABSENT, motif_taille_inconnue('x'))


class ContratPlanImporteTest(SimpleTestCase):
    """Le contrat committé et la porte disent la MÊME chose."""

    def test_l_echantillon_porte_les_trois_cles_de_PACT10(self):
        contrat = _contrat()
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, contrat)

    def test_l_endpoint_est_celui_de_la_route(self):
        self.assertTrue(_contrat()['endpoint'].endswith('/plan-importe/'))

    def test_l_exemple_porte_exactement_les_huit_cles_servies(self):
        self.assertEqual(sorted(_contrat()['exemple']),
                         sorted(CLES_DU_CONTRAT))

    def test_l_exemple_servi_ne_porte_aucun_motif(self):
        """Tout est servi ⇒ `motif` vide : un motif de complaisance mentirait."""
        exemple = _contrat()['exemple']
        self.assertEqual(exemple['motif'], '')
        self.assertGreater(exemple['largeur'], 0)
        self.assertGreater(exemple['hauteur'], 0)

    def test_l_exemple_sans_taille_porte_le_motif_de_la_porte(self):
        exemple = _contrat()['exemple_taille_inconnue']
        self.assertIsNone(exemple['largeur'])
        self.assertIsNone(exemple['hauteur'])
        self.assertEqual(exemple['motif'],
                         motif_taille_inconnue(exemple['filename']))

    def test_l_exemple_de_refus_porte_le_motif_de_la_porte(self):
        refus = _contrat()['exemple_refus_photo']
        self.assertEqual(refus['detail'], FOND_PHOTO)
        self.assertEqual(refus['champ'], 'kind')

    def test_aucune_url_de_chemin_disque_dans_les_exemples(self):
        """Une URL servie, jamais un chemin de fichier local."""
        for cle in ('exemple', 'exemple_taille_inconnue'):
            self.assertTrue(_contrat()[cle]['url'].startswith('https://'))


class PlanImporteApiTest(TestCase):
    """L'API réelle — EXIGE LA BASE, non exécutée sur le poste de la lane.

    Elle arme les promesses de la tâche : 200 à la forme du contrat quand le
    document désigne une pièce rattachée, 404 NOMMÉ dans les quatre cas
    d'absence, et 404 (introuvable, jamais « interdit ») pour un calepinage
    d'une AUTRE société.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        from apps.calepinage.models import Calepinage
        from apps.crm.models import Lead
        from apps.records.models import Attachment
        from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
        from authentication.models import Company

        self.company = Company.objects.create(nom='Plan Co',
                                              slug='plan-co-107')
        self.autre = Company.objects.create(nom='Voisine Co',
                                            slug='voisine-co-107')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = get_user_model().objects.create_user(
            username='poseur_107', password='x', company=self.company,
            role=role)
        lead = Lead.objects.create(company=self.company, nom='Toiture A')
        lead_autre = Lead.objects.create(company=self.autre,
                                         nom='Toiture B')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='Toiture A',
            roof_layout={'version': 2, 'zones': []})
        self.calepinage_autre = Calepinage.objects.create(
            company=self.autre, lead_id=lead_autre.pk, titre='Toiture B',
            roof_layout={'version': 2, 'zones': []})
        self.piece = Attachment.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk,
            file_key='roofs/%d/calepinage-%d-plan.png'
                     % (self.company.pk, self.calepinage.pk),
            filename='plan-masse.png', size=128, mime='image/png')
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _url(self, calepinage):
        return ('/api/django/calepinage/calepinages/%d/plan-importe/'
                % calepinage.pk)

    def _poser_fond(self, fond):
        self.calepinage.roof_layout = {'version': 2, 'zones': [],
                                       'underlay': fond}
        self.calepinage.save(update_fields=['roof_layout'])

    def test_200_a_la_forme_du_contrat(self):
        self._poser_fond({'kind': 'plan', 'attachmentId': self.piece.pk})

        reponse = self.client.get(self._url(self.calepinage))

        self.assertEqual(reponse.status_code, 200)
        servi = reponse.json()
        self.assertEqual(sorted(servi), sorted(CLES_DU_CONTRAT))
        self.assertEqual(servi['attachment'], self.piece.pk)
        self.assertEqual(servi['filename'], 'plan-masse.png')
        # Le magasin d'objets n'a pas l'objet en test : la taille est
        # INCONNUE et le motif le DIT — jamais un gabarit supposé.
        self.assertIsNone(servi['largeur'])
        self.assertIsNone(servi['hauteur'])
        self.assertTrue(servi['motif'])

    def test_404_nomme_quand_le_document_ne_demande_aucun_fond(self):
        reponse = self.client.get(self._url(self.calepinage))

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.json()['champ'], 'underlay')

    def test_404_nomme_quand_le_fond_est_une_photo(self):
        self._poser_fond({'kind': 'photo', 'photoSiteId': 7})

        reponse = self.client.get(self._url(self.calepinage))

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.json()['champ'], 'kind')
        self.assertEqual(reponse.json()['detail'], FOND_PHOTO)

    def test_404_nomme_quand_le_plan_ne_designe_aucune_piece(self):
        self._poser_fond({'kind': 'plan'})

        reponse = self.client.get(self._url(self.calepinage))

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.json()['champ'], 'attachmentId')
        self.assertEqual(reponse.json()['detail'], SANS_PIECE)

    def test_404_quand_la_piece_appartient_a_un_autre_dossier(self):
        self._poser_fond({'kind': 'plan', 'attachmentId': self.piece.pk})
        self.piece.object_id = self.calepinage_autre.pk
        self.piece.save(update_fields=['object_id'])

        reponse = self.client.get(self._url(self.calepinage))

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.json()['detail'], PIECE_INTROUVABLE)

    def test_404_pour_un_calepinage_d_une_autre_societe(self):
        reponse = self.client.get(self._url(self.calepinage_autre))

        self.assertEqual(reponse.status_code, 404)

    def test_aucune_ecriture(self):
        self._poser_fond({'kind': 'plan', 'attachmentId': self.piece.pk})
        avant = (self.calepinage.statut, self.calepinage.resultat)

        self.client.get(self._url(self.calepinage))

        self.calepinage.refresh_from_db()
        self.assertEqual((self.calepinage.statut, self.calepinage.resultat),
                         avant)
