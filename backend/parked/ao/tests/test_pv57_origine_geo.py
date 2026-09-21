"""PV57 — ``ToitureAO`` sait enfin dire OÙ elle est.

Le repère local d'une toiture est métrique et RELATIF (AOF18) : sans point
d'ancrage, aucune toiture relevée ne peut être reprojetée sur une carte ni
recoupée avec une image satellite. Deux champs nullables ferment le trou.

Ce que ce module VERROUILLE :

  1. **L'aller-retour API est exact** — ce qu'on écrit est ce qu'on relit, à la
     7ᵉ décimale (≈ 1 cm), et non arrondi en route.
  2. **``null`` reste la valeur JUSTE** pour une toiture sans ancre : une
     toiture saisie sur plan papier n'en a légitimement aucune, et un ``0.0``
     désignerait le golfe de Guinée.
  3. **Chaque axe est NOMMÉ** (``lat`` / ``lng``) : c'est la parade au piège
     documenté du dépôt — le lecteur de cartes sérialise en ``[lng, lat]``, le
     lead CRM en ``[lat, lng]``, et une paire anonyme rendrait l'inversion
     indétectable.
  4. **L'ajout est ADDITIF** : aucune toiture existante n'est touchée.

Run :
    python manage.py test apps.ao.tests.test_pv57_origine_geo -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre, BatimentAO, ToitureAO
from apps.ao.serializers import ToitureAOSerializer
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/toitures/'

#: Casablanca — l'ancre exacte d'un relevé réel, à la 7ᵉ décimale (≈ 1 cm).
LAT, LNG = '33.5731245', '-7.5898431'


class BasePv57(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV57 Co', slug='pv57-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='pv57_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-57-1', objet='Ancre géo')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')

    def _corps(self, **surcharges):
        corps = {'batiment': self.batiment.pk, 'code_document': '05H',
                 'forme': 'polygone',
                 'contour_local_m': [[0, 0], [30, 0], [30, 18], [0, 18]]}
        corps.update(surcharges)
        return corps


class LAllerRetourEstExact(BasePv57):
    def test_creation_puis_relecture_par_l_API(self):
        creation = self.api.post(
            URL, self._corps(origine_lat=LAT, origine_lng=LNG), format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        toiture = ToitureAO.objects.get(pk=creation.data['id'])
        self.assertEqual(toiture.origine_lat, Decimal(LAT))
        self.assertEqual(toiture.origine_lng, Decimal(LNG))

        relecture = self.api.get(f'{URL}{toiture.pk}/')
        self.assertEqual(relecture.status_code, 200)
        self.assertEqual(Decimal(relecture.data['origine_lat']), Decimal(LAT))
        self.assertEqual(Decimal(relecture.data['origine_lng']), Decimal(LNG))

    def test_la_septieme_decimale_survit(self):
        """≈ 1 cm : un arrondi en route déplacerait la toiture sur la carte."""
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment,
            code_document='06H', forme=ToitureAO.Forme.POLYGONE,
            contour_local_m=[[0, 0], [10, 0], [10, 10], [0, 10]],
            origine_lat=Decimal(LAT), origine_lng=Decimal(LNG))
        toiture.refresh_from_db()
        self.assertEqual(str(toiture.origine_lat), LAT)
        self.assertEqual(str(toiture.origine_lng), LNG)

    def test_une_longitude_negative_reste_negative(self):
        """Le Maroc est à l'OUEST de Greenwich : le signe n'est pas décoratif."""
        creation = self.api.post(
            URL, self._corps(origine_lat=LAT, origine_lng=LNG), format='json')
        self.assertLess(Decimal(creation.data['origine_lng']), 0)

    def test_modification_partielle(self):
        creation = self.api.post(URL, self._corps(), format='json')
        identifiant = creation.data['id']
        reponse = self.api.patch(f'{URL}{identifiant}/',
                                 {'origine_lat': LAT, 'origine_lng': LNG},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        toiture = ToitureAO.objects.get(pk=identifiant)
        self.assertEqual(toiture.origine_lat, Decimal(LAT))


class SansAncreCEstNullEtNonZero(BasePv57):
    """Une toiture saisie sur plan papier n'a légitimement aucune ancre."""

    def test_les_deux_champs_sont_nuls_par_defaut(self):
        creation = self.api.post(URL, self._corps(), format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        toiture = ToitureAO.objects.get(pk=creation.data['id'])
        self.assertIsNone(toiture.origine_lat)
        self.assertIsNone(toiture.origine_lng)
        self.assertIsNone(creation.data['origine_lat'])
        self.assertIsNone(creation.data['origine_lng'])

    def test_null_est_accepte_explicitement(self):
        creation = self.api.post(
            URL, self._corps(origine_lat=None, origine_lng=None),
            format='json')
        self.assertEqual(creation.status_code, 201, creation.data)
        self.assertIsNone(creation.data['origine_lat'])

    def test_le_champ_reste_facultatif_dans_le_serialiseur(self):
        for nom in ('origine_lat', 'origine_lng'):
            champ = ToitureAOSerializer().fields[nom]
            self.assertFalse(champ.required, nom)
            self.assertTrue(champ.allow_null, nom)


class LAjoutEstAdditif(BasePv57):
    def test_une_toiture_sans_ancre_reste_valide_et_calculable(self):
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment,
            code_document='07H', forme=ToitureAO.Forme.POLYGONE,
            contour_local_m=[[0, 0], [10, 0], [10, 10], [0, 10]])
        toiture.clean()
        self.assertIsNone(toiture.origine_lat)

    def test_les_deux_axes_sont_NOMMES_et_distincts(self):
        noms = {champ.name for champ in ToitureAO._meta.local_fields}
        self.assertIn('origine_lat', noms)
        self.assertIn('origine_lng', noms)
        # aucune paire anonyme (``origine``, ``coordonnees``…) : l'inversion
        # lat/lng doit rester détectable à la lecture du schéma.
        self.assertNotIn('origine', noms)
        self.assertNotIn('coordonnees', noms)
