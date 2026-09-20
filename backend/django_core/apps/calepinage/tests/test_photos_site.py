"""CAL52 — la photo drone / oblique du site : reçue, rangée, jamais devinée.

CE QUI EST PROUVÉ ICI
---------------------
* **UN SEUL MAGASIN** — les octets passent par les fonctions minces
  d'``apps.ventes.services`` (celles de ``roof-image``, CAL19), la clé est
  DÉRIVÉE côté serveur et porte la société (``roofs/<company_id>/…``) ;
* **AUCUN champ fichier** — la ligne de fichier est un ``records.Attachment``
  rattaché au calepinage par ``ContentType`` ;
* **la date de prise de vue est SAISIE** — absente, illisible ou future, la
  photo est refusée en NOMMANT ``prise_le`` ; jamais la date d'import ;
* un fichier NON-IMAGE est refusé (magic-bytes du chemin ventes), et un refus
  ne laisse RIEN en base ;
* la relecture rend une URL pré-signée et toutes les clés, ``calage`` à
  ``null`` tant que CAL53 n'a pas posé de calage ;
* l'isolation société tient : le calepinage d'une autre société est
  INTROUVABLE (404), même avec un fichier valide ;
* aucun statut ne bouge (règle #4).

Le stockage MinIO est remplacé par un double : aucun test ne sort.

Run :
    python manage.py test apps.calepinage.tests.test_photos_site -v2
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage, PhotoSite
from apps.calepinage.selectors import photos_site
from apps.calepinage.services.photos import (
    PhotoRefusee,
    ajouter_photo_site,
)
from apps.crm.models import Lead
from apps.records.models import Attachment
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

#: Un PNG minimal (signature + IHDR) : les magic-bytes du chemin ventes.
PNG = (b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR'
       + b'\x00' * 40)
PAS_UNE_IMAGE = b'%PDF-1.4 ceci est un PDF, pas une photo'

HIER = datetime.date.today() - datetime.timedelta(days=1)
DEMAIN = datetime.date.today() + datetime.timedelta(days=1)


def _fichier(octets=PNG, nom='vol-drone.png'):
    return SimpleUploadedFile(nom, octets, content_type='image/png')


class BasePhoto(TestCase):
    """Deux sociétés, un calepinage, et un stockage remplacé par un double."""

    def setUp(self):
        self.company = Company.objects.create(nom='Photo Co',
                                              slug='photo-co-52')
        self.autre = Company.objects.create(nom='Voisine Photo',
                                            slug='voisine-photo-52')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='cal52', password='x', company=self.company,
            role=self.role)
        self.lead = Lead.objects.create(company=self.company, nom='Toit Anfa')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit Anfa')

        self.stocke = mock.patch(
            'apps.ventes.services.stocker_image_toiture').start()
        self.url_presignee = mock.patch(
            'apps.ventes.services.url_image_toiture',
            return_value='https://minio/presigne').start()
        self.addCleanup(mock.patch.stopall)

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.user)}'))
        return api


class ServiceTest(BasePhoto):
    """Le chemin d'écriture : un magasin, une pièce jointe, une date saisie."""

    def test_photo_rangee_dans_le_magasin_ventes(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   genre='drone', prise_le=HIER,
                                   user=self.user)
        self.assertEqual(self.stocke.call_count, 1)
        cle = self.stocke.call_args[0][1]
        self.assertTrue(cle.startswith(f'roofs/{self.company.pk}/'), cle)
        self.assertIn(f'calepinage-{self.calepinage.pk}-photo-', cle)
        self.assertTrue(cle.endswith('.png'), cle)
        self.assertEqual(photo.attachment.file_key, cle)

    def test_la_piece_jointe_cible_le_calepinage(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   prise_le=HIER, user=self.user)
        piece = photo.attachment
        self.assertEqual(piece.content_type,
                         ContentType.objects.get_for_model(Calepinage))
        self.assertEqual(piece.object_id, self.calepinage.pk)
        self.assertEqual(piece.company, self.company)
        self.assertEqual(piece.filename, 'vol-drone.png')
        self.assertEqual(piece.size, len(PNG))

    def test_la_societe_et_l_auteur_viennent_du_serveur(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   prise_le=HIER, user=self.user)
        self.assertEqual(photo.company, self.company)
        self.assertEqual(photo.ajoutee_par, self.user)

    def test_genre_par_defaut_drone(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   prise_le=HIER)
        self.assertEqual(photo.genre, PhotoSite.Genre.DRONE)

    def test_genre_oblique_accepte(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   genre='oblique', prise_le=HIER)
        self.assertEqual(photo.genre, 'oblique')

    def test_date_texte_acceptee(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   prise_le=HIER.isoformat())
        self.assertEqual(photo.prise_le, HIER)

    def test_calage_vide_attend_cal53(self):
        photo = ajouter_photo_site(self.calepinage, _fichier(),
                                   prise_le=HIER)
        self.assertIsNone(photo.calage)

    def test_aucun_statut_ne_bouge(self):
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=HIER)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.statut, Calepinage.Statut.BROUILLON)

    def test_plusieurs_photos_ont_des_cles_distinctes(self):
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=HIER)
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=HIER)
        cles = {p.attachment.file_key for p in PhotoSite.objects.all()}
        self.assertEqual(len(cles), 2)


class RefusTest(BasePhoto):
    """Chaque refus nomme SON champ, et ne laisse rien derrière lui."""

    def _refus(self, champ, **kwargs):
        kwargs.setdefault('fichier', _fichier())
        fichier = kwargs.pop('fichier')
        with self.assertRaises(PhotoRefusee) as capture:
            ajouter_photo_site(self.calepinage, fichier, **kwargs)
        self.assertEqual(capture.exception.champ, champ,
                         str(capture.exception))
        return capture.exception

    def test_date_manquante_refusee(self):
        erreur = self._refus('prise_le')
        self.assertIn('SAISIE', str(erreur))

    def test_date_illisible_refusee(self):
        self._refus('prise_le', prise_le='hier matin')

    def test_date_future_refusee(self):
        self._refus('prise_le', prise_le=DEMAIN)

    def test_genre_inconnu_refuse(self):
        self._refus('genre', genre='satellite', prise_le=HIER)

    def test_fichier_manquant_refuse(self):
        self._refus('photo', fichier=None, prise_le=HIER)

    def test_fichier_non_image_refuse(self):
        self._refus('photo', fichier=_fichier(PAS_UNE_IMAGE, 'plan.pdf'),
                    prise_le=HIER)

    def test_fichier_vide_refuse(self):
        self._refus('photo', fichier=_fichier(b'', 'vide.png'),
                    prise_le=HIER)

    def test_un_refus_ne_laisse_rien_en_base(self):
        for cas in ({}, {'prise_le': DEMAIN},
                    {'prise_le': HIER, 'genre': 'satellite'}):
            with self.assertRaises(PhotoRefusee):
                ajouter_photo_site(self.calepinage, _fichier(), **cas)
        self.assertEqual(PhotoSite.objects.count(), 0)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_un_refus_de_formulaire_ne_televerse_rien(self):
        """Date et genre sont validés AVANT le téléversement."""
        with self.assertRaises(PhotoRefusee):
            ajouter_photo_site(self.calepinage, _fichier(), prise_le=DEMAIN)
        self.assertEqual(self.stocke.call_count, 0)


class LectureTest(BasePhoto):
    """La relecture : toutes les clés, une URL pré-signée, le bon ordre."""

    def test_liste_vide_rend_une_liste(self):
        self.assertEqual(photos_site(self.calepinage), [])

    def test_clefs_toujours_presentes(self):
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=HIER,
                           legende='Vol du matin', user=self.user)
        ligne = photos_site(self.calepinage)[0]
        self.assertEqual(sorted(ligne), sorted([
            'id', 'genre', 'prise_le', 'legende', 'calage', 'file_key',
            'filename', 'mime', 'size', 'url', 'ajoutee_par', 'created_at']))
        self.assertEqual(ligne['url'], 'https://minio/presigne')
        self.assertEqual(ligne['prise_le'], HIER.isoformat())
        self.assertEqual(ligne['legende'], 'Vol du matin')
        self.assertIsNone(ligne['calage'])

    def test_ordre_par_date_de_prise_de_vue(self):
        vieille = HIER - datetime.timedelta(days=30)
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=vieille,
                           legende='ancienne')
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=HIER,
                           legende='récente')
        lignes = photos_site(self.calepinage)
        self.assertEqual([ligne['legende'] for ligne in lignes],
                         ['récente', 'ancienne'])


class EndpointTest(BasePhoto):
    """``calepinages/<pk>/photos/`` — l'objet d'abord, puis le fichier."""

    def setUp(self):
        super().setUp()
        self.url = ('/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/photos/')
        self.api = self._api()

    def test_get_liste_les_photos(self):
        ajouter_photo_site(self.calepinage, _fichier(), prise_le=HIER)
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data['photos']), 1)

    def test_post_range_la_photo(self):
        reponse = self.api.post(
            self.url,
            {'photo': _fichier(), 'prise_le': HIER.isoformat(),
             'genre': 'drone', 'legende': 'Vol du matin'},
            format='multipart')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(reponse.data['photo']['legende'], 'Vol du matin')
        self.assertEqual(len(reponse.data['photos']), 1)
        self.assertEqual(PhotoSite.objects.count(), 1)

    def test_post_sans_date_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(self.url, {'photo': _fichier()},
                                format='multipart')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('prise_le', reponse.data)
        self.assertEqual(PhotoSite.objects.count(), 0)

    def test_post_non_image_refuse(self):
        reponse = self.api.post(
            self.url,
            {'photo': _fichier(PAS_UNE_IMAGE, 'plan.pdf'),
             'prise_le': HIER.isoformat()},
            format='multipart')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('photo', reponse.data)

    def test_calepinage_d_une_autre_societe_introuvable(self):
        """L'OBJET D'ABORD : 404, jamais un oracle d'existence."""
        role = Role.objects.create(company=self.autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        voisin = User.objects.create_user(username='cal52_voisin',
                                          password='x', company=self.autre,
                                          role=role)
        reponse = self._api(voisin).post(
            self.url, {'photo': _fichier(), 'prise_le': HIER.isoformat()},
            format='multipart')
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(PhotoSite.objects.count(), 0)
