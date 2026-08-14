"""PV54 — ``ZoneAO`` : le contour NOMMÉ qu'aucun écran ne savait saisir.

Le moteur (``core.calepinage.zones``) consomme quatre natures de zone depuis
AOF57 ; ``calepinage_io`` lui envoyait pourtant ``zones: []`` en dur, faute
d'un endroit où les saisir. Ce modèle est cet endroit.

Ce que ce module VERROUILLE :

  1. **Les quatre natures sont celles du MOTEUR**, à la lettre — une nature
     inventée ici serait refusée à la désérialisation du contrat, loin de la
     saisie qui l'a produite.
  2. **CRUD complet** sous ``/api/django/ao/zones/``, gardé comme les
     obstacles (``ao_voir`` / ``ao_gerer``).
  3. **Cloisonnement société** : la zone d'un autre tenant est INTROUVABLE
     (404), et ``company`` n'est jamais lue du corps de la requête — même
     envoyée explicitement, c'est celle de l'appelant qui est posée.
  4. **Un contour qui n'en est pas un est refusé** en français, champ nommé.

Run :
    python manage.py test apps.ao.tests.test_pv54_zones -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre, BatimentAO, ToitureAO, ZoneAO
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core.calepinage.types import NatureZone

User = get_user_model()

URL = '/api/django/ao/zones/'
CARRE = [[2.0, 2.0], [6.0, 2.0], [6.0, 6.0], [2.0, 6.0]]


def resultats(reponse):
    """Les lignes d'une liste, paginée ou non — la pagination est transverse."""
    donnees = reponse.data
    return donnees['results'] if isinstance(donnees, dict) else donnees


class LesNaturesSontCellesDuMoteur(SimpleTestCase):
    """Une cinquième nature inventée ici serait refusée par le contrat."""

    def test_les_quatre_valeurs_sont_identiques_a_naturezone(self):
        self.assertEqual({v for v, _ in ZoneAO.Nature.choices},
                         {n.value for n in NatureZone})

    def test_chaque_valeur_est_lisible_par_le_moteur(self):
        for valeur, _libelle in ZoneAO.Nature.choices:
            self.assertEqual(NatureZone(valeur).value, valeur)


class BaseZone(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV54 Co', slug='pv54-co')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='pv54_dir', password='x', company=self.company,
            role=self.role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.toiture = self._toiture(self.company, 'AO-54-1', 'C')

    @staticmethod
    def _toiture(company, reference, code):
        ao = AppelOffre.objects.create(
            company=company, reference=reference, objet='Zones')
        batiment = BatimentAO.objects.create(
            company=company, appel_offre=ao, code=code)
        return ToitureAO.objects.create(
            company=company, batiment=batiment, code_document=f'{code}-05H',
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]])

    def _voisin(self):
        """Une DEUXIÈME société, avec son propre utilisateur et sa toiture."""
        autre = Company.objects.create(nom='PV54 Voisin', slug='pv54-voisin')
        role = Role.objects.create(company=autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='pv54_voisin', password='x',
                                        company=autre, role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return autre, client, self._toiture(autre, 'AO-54-Z', 'Z')

    def _creer(self, **surcharges):
        corps = {'toiture': self.toiture.pk, 'repere': 'Z1',
                 'nature': ZoneAO.Nature.INTERDITE, 'sommets': CARRE,
                 'retrait_m': '0.00'}
        corps.update(surcharges)
        return self.api.post(URL, corps, format='json')


class LeCrudComplet(BaseZone):
    def test_creation(self):
        reponse = self._creer()
        self.assertEqual(reponse.status_code, 201, reponse.data)
        zone = ZoneAO.objects.get(pk=reponse.data['id'])
        self.assertEqual(zone.company_id, self.company.pk)
        self.assertEqual(zone.toiture_id, self.toiture.pk)
        self.assertEqual(zone.nature, ZoneAO.Nature.INTERDITE)
        self.assertEqual(zone.sommets, CARRE)
        self.assertEqual(zone.retrait_m, Decimal('0.00'))
        self.assertTrue(reponse.data['exploitable'])
        self.assertEqual(reponse.data['nature_display'], 'Zone interdite')

    def test_lecture_liste_et_detail(self):
        identifiant = self._creer().data['id']
        liste = self.api.get(URL)
        self.assertEqual(liste.status_code, 200)
        self.assertEqual([z['id'] for z in resultats(liste)], [identifiant])
        detail = self.api.get(f'{URL}{identifiant}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['repere'], 'Z1')

    def test_modification(self):
        identifiant = self._creer().data['id']
        reponse = self.api.patch(
            f'{URL}{identifiant}/',
            {'nature': ZoneAO.Nature.PREFEREE, 'retrait_m': '0.25'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        zone = ZoneAO.objects.get(pk=identifiant)
        self.assertEqual(zone.nature, ZoneAO.Nature.PREFEREE)
        self.assertEqual(zone.retrait_m, Decimal('0.25'))

    def test_suppression(self):
        identifiant = self._creer().data['id']
        reponse = self.api.delete(f'{URL}{identifiant}/')
        self.assertEqual(reponse.status_code, 204)
        self.assertFalse(ZoneAO.objects.filter(pk=identifiant).exists())

    def test_filtre_par_toiture_et_par_nature(self):
        self._creer(repere='Z1', nature=ZoneAO.Nature.INTERDITE)
        self._creer(repere='Z2', nature=ZoneAO.Nature.PREFEREE)
        reponse = self.api.get(URL, {'nature': ZoneAO.Nature.PREFEREE})
        self.assertEqual([z['repere'] for z in resultats(reponse)], ['Z2'])
        reponse = self.api.get(URL, {'toiture': self.toiture.pk})
        self.assertEqual(len(resultats(reponse)), 2)

    def test_filtre_par_appel_offre(self):
        self._creer()
        reponse = self.api.get(
            URL, {'appel_offre': self.toiture.batiment.appel_offre_id})
        self.assertEqual(len(resultats(reponse)), 1)


class LeCloisonnementSociete(BaseZone):
    """Une zone d'une autre société n'existe pas pour cet appelant."""

    def test_la_liste_ne_montre_que_les_zones_de_la_societe(self):
        self._creer()
        _autre, client, toiture = self._voisin()
        ZoneAO.objects.create(company=toiture.company, toiture=toiture,
                              repere='ZX', sommets=CARRE)
        reponse = self.api.get(URL)
        self.assertEqual([z['repere'] for z in resultats(reponse)], ['Z1'])
        chez_le_voisin = client.get(URL)
        self.assertEqual([z['repere'] for z in resultats(chez_le_voisin)],
                         ['ZX'])

    def test_la_zone_d_une_autre_societe_est_introuvable(self):
        _autre, _client, toiture = self._voisin()
        etrangere = ZoneAO.objects.create(
            company=toiture.company, toiture=toiture, repere='ZX',
            sommets=CARRE)
        detail = self.api.get(f'{URL}{etrangere.pk}/')
        self.assertEqual(detail.status_code, 404)
        suppression = self.api.delete(f'{URL}{etrangere.pk}/')
        self.assertEqual(suppression.status_code, 404)
        self.assertTrue(ZoneAO.objects.filter(pk=etrangere.pk).exists())

    def test_la_societe_du_corps_de_requete_est_IGNOREE(self):
        """``company`` est posée côté serveur, jamais lue du corps."""
        autre, _client, _toiture = self._voisin()
        reponse = self._creer(company=autre.pk)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        zone = ZoneAO.objects.get(pk=reponse.data['id'])
        self.assertEqual(zone.company_id, self.company.pk)

    def test_la_societe_n_est_pas_un_champ_du_serialiseur(self):
        from apps.ao.serializers import ZoneAOSerializer

        self.assertNotIn('company', ZoneAOSerializer().fields)


class UnContourQuiNEnEstPasUnEstRefuse(BaseZone):
    """Une zone à deux sommets ferait échouer un calcul loin de sa saisie."""

    def test_deux_sommets(self):
        reponse = self._creer(sommets=[[0.0, 0.0], [1.0, 1.0]])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('sommets', reponse.data)

    def test_un_sommet_qui_n_est_pas_un_couple(self):
        reponse = self._creer(sommets=[[0.0, 0.0], [1.0, 1.0], [2.0]])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('sommets', reponse.data)

    def test_une_coordonnee_qui_n_est_pas_un_nombre(self):
        reponse = self._creer(
            sommets=[[0.0, 0.0], [1.0, 1.0], ['en haut', 2.0]])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('sommets', reponse.data)

    def test_un_retrait_negatif(self):
        reponse = self._creer(retrait_m='-0.10')
        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_un_contour_vide_reste_permis_mais_non_exploitable(self):
        """Une zone en cours de saisie a le droit d'exister sans son tracé."""
        reponse = self._creer(sommets=[])
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertFalse(reponse.data['exploitable'])

    def test_le_modele_refuse_aussi_hors_API(self):
        zone = ZoneAO(company=self.company, toiture=self.toiture,
                      sommets=[[0.0, 0.0], [1.0, 1.0]])
        with self.assertRaises(ValidationError):
            zone.clean()

    def test_deux_zones_de_meme_repere_sur_une_toiture_sont_refusees(self):
        from django.db import IntegrityError, transaction

        self._creer(repere='Z1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ZoneAO.objects.create(company=self.company,
                                      toiture=self.toiture, repere='Z1',
                                      sommets=CARRE)
