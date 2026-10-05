"""ACAL202 — photos de site : PATCH/DELETE d'une photo, calage dégénéré refusé,
clé ``calage`` obligatoire, identifiant non numérique 404.

Constat C-ACAL-020/021 : une date de prise de vue mal saisie ne se corrigeait
pas (aucun PATCH), une photo ne se retirait pas (aucun DELETE), un calage à
coins confondus/alignés/croisés passait, et un PATCH ``calage/`` SANS la clé
effaçait le calage en silence (``request.data.get('calage')`` ⇒ ``None``).

Le stockage MinIO est remplacé par un double : aucun test ne sort.

Run :
    python manage.py test apps.calepinage.tests.test_acal_photos_edition -v2
"""
import datetime

from apps.calepinage.models import PhotoSite
from apps.calepinage.services.photos import (
    ajouter_photo_site,
    calage_photo_site,
)
from apps.calepinage.tests.test_photos_site import (
    BasePhoto,
    COINS,
    HIER,
    DEMAIN,
    _fichier,
)
from apps.records.models import Attachment
from core.calepinage.calage import CalageInvalide, valider_quatre_coins

AVANT_HIER = datetime.date.today() - datetime.timedelta(days=2)

#: Quatre fois le même point.
IDENTIQUES = [[33.5731, -7.5898]] * 4
#: Quatre points sur une même droite.
COLINEAIRES = [[33.5731, -7.5898], [33.5732, -7.5898],
               [33.5733, -7.5898], [33.5734, -7.5898]]
#: Le « nœud papillon » : les coins 2 et 3 de COINS intervertis.
CROISES = [COINS[0], COINS[2], COINS[1], COINS[3]]


class EditionPhotoTest(BasePhoto):
    """``calepinages/<pk>/photos/<id>/`` — PATCH et DELETE."""

    def setUp(self):
        super().setUp()
        self.api = self._api()
        self.photo = ajouter_photo_site(self.calepinage, _fichier(),
                                        genre='drone', prise_le=HIER,
                                        legende='Vol nord', user=self.user)
        self.base = ('/api/django/calepinage/calepinages/'
                     f'{self.calepinage.pk}/photos/')
        self.url = f'{self.base}{self.photo.pk}/'

    def test_patch_photo_met_a_jour_genre_date_legende(self):
        reponse = self.api.patch(
            self.url, {'genre': 'oblique', 'prise_le': AVANT_HIER.isoformat(),
                       'legende': 'Vol sud'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['photo']['genre'], 'oblique')
        # Persistance : relue par GET photos/.
        lignes = self.api.get(self.base).data['photos']
        ligne = next(x for x in lignes if x['id'] == self.photo.pk)
        self.assertEqual(ligne['prise_le'], AVANT_HIER.isoformat())
        self.assertEqual(ligne['genre'], 'oblique')
        self.assertEqual(ligne['legende'], 'Vol sud')

    def test_patch_date_future_refusee_comme_a_la_creation(self):
        reponse = self.api.patch(self.url, {'prise_le': DEMAIN.isoformat()},
                                 format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('prise_le', reponse.data)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.prise_le, HIER)

    def test_patch_genre_inconnu_refuse(self):
        reponse = self.api.patch(self.url, {'genre': 'satellite'},
                                 format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('genre', reponse.data)

    def test_patch_partiel_ne_touche_que_les_cles_presentes(self):
        reponse = self.api.patch(self.url, {'legende': 'Corrigée'},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.legende, 'Corrigée')
        self.assertEqual(self.photo.prise_le, HIER)
        self.assertEqual(self.photo.genre, 'drone')

    def test_delete_photo_retire_la_piece(self):
        piece_id = self.photo.attachment_id
        reponse = self.api.delete(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(PhotoSite.objects.filter(pk=self.photo.pk).exists())
        self.assertFalse(Attachment.objects.filter(pk=piece_id).exists())
        # Persistance : absente au GET.
        lignes = self.api.get(self.base).data['photos']
        self.assertNotIn(self.photo.pk, [x['id'] for x in lignes])

    def test_photo_d_une_autre_societe_introuvable(self):
        from django.contrib.auth import get_user_model

        from apps.roles.models import Role
        from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS

        role = Role.objects.create(company=self.autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        voisin = get_user_model().objects.create_user(
            username='acal202_voisin', password='x', company=self.autre,
            role=role)
        self.assertEqual(self._api(voisin).delete(self.url).status_code, 404)
        self.assertEqual(self._api(voisin).patch(
            self.url, {'legende': 'x'}, format='json').status_code, 404)
        self.assertTrue(PhotoSite.objects.filter(pk=self.photo.pk).exists())

    def test_id_non_numerique_404(self):
        for url in (f'{self.base}abc/calage/', f'{self.base}abc/'):
            reponse = self.api.patch(url, {'calage': {'coins': COINS}},
                                     format='json')
            self.assertEqual(reponse.status_code, 404, url)


class CalageDegenereTest(BasePhoto):
    """Le validateur unique refuse les quadrilatères dégénérés."""

    def setUp(self):
        super().setUp()
        self.api = self._api()
        self.photo = ajouter_photo_site(self.calepinage, _fichier(),
                                        prise_le=HIER)
        self.url = ('/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/photos/{self.photo.pk}/calage/')

    def test_calage_degenere_refuse_400(self):
        for nom, coins in (('identiques', IDENTIQUES),
                           ('colineaires', COLINEAIRES),
                           ('croises', CROISES)):
            with self.subTest(nom):
                reponse = self.api.patch(self.url, {'calage': {'coins': coins}},
                                         format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn('calage', reponse.data)
        self.photo.refresh_from_db()
        self.assertIsNone(self.photo.calage)

    def test_quadrilatere_convexe_200(self):
        reponse = self.api.patch(self.url, {'calage': {'coins': COINS}},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_corps_sans_cle_calage_400_et_calage_conserve(self):
        calage_photo_site(self.photo, {'coins': COINS})
        reponse = self.api.patch(self.url, {'autre': 1}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('calage', reponse.data)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.calage, {'coins': COINS})

    def test_calage_non_objet_400(self):
        reponse = self.api.patch(self.url, {'calage': 'n/a'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('calage', reponse.data)

    def test_null_explicite_efface(self):
        calage_photo_site(self.photo, {'coins': COINS})
        reponse = self.api.patch(self.url, {'calage': None}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.photo.refresh_from_db()
        self.assertIsNone(self.photo.calage)


class ValideurPurTest(BasePhoto):
    """Le survivant pur ``core.calepinage.calage`` — sans HTTP."""

    def test_valide_et_normalise(self):
        self.assertEqual(valider_quatre_coins({'coins': COINS}),
                         {'coins': COINS})

    def test_refuse_les_trois_degenerescences(self):
        for coins in (IDENTIQUES, COLINEAIRES, CROISES):
            with self.assertRaises(CalageInvalide):
                valider_quatre_coins({'coins': coins})

    def test_ordre_inverse_accepte(self):
        valider_quatre_coins({'coins': list(reversed(COINS))})
