"""ACAL129 — fuseau du site : repli sur le fuseau SAISI du profil société,
avec provenance publiée, et servi à l'écran (``imagerie.site_effectif``).

Constat C-ACAL-066 : sans ``ParametresCalepinage.imagerie.fuseau``, les blocs
autoconsommation / batterie / hors réseau étaient omis
(MOTIF_FUSEAU_ABSENT) alors que la société avait SAISI son fuseau dans son
profil (``CompanyProfile.fuseau_horaire``).

Désormais ``services/site.fuseau_du_site(section, *, company=None)`` reste
LA fonction : l'imagerie prime, sinon le profil société (provenance
``profil_societe`` + mention) ; jamais la longitude.

Chaîne RÉELLE, société et profil RÉELS en base de test ; aucun mock.

Run :
    python manage.py test apps.calepinage.tests.test_acal_fuseau_site -v2
"""
from __future__ import annotations

import copy

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.services.chaine_pertes import MOTIF_FUSEAU_ABSENT
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.services.site import (
    MENTION_FUSEAU_PROFIL, PROVENANCE_IMAGERIE, PROVENANCE_PROFIL_SOCIETE,
    fuseau_du_site,
)
from apps.parametres.models_company import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .test_calx5_simulation import (
    MATERIEL, REGLAGES, _Calepinage, _ClientRejoue,
)

URL_PARAMETRES = '/api/django/calepinage/parametres/'


def _simuler(company, reglages=None):
    calepinage = _Calepinage()
    calepinage.company = company
    return simuler_calepinage(calepinage, client=_ClientRejoue(),
                              materiel=MATERIEL,
                              reglages=reglages or REGLAGES,
                              enregistrer=False)['blocs']


class FuseauDuSiteTest(TestCase):

    def setUp(self):
        self.societe = Company.objects.create(nom='ACAL129', slug='acal129')

    def _profil(self, fuseau='Africa/Casablanca'):
        CompanyProfile.objects.create(company=self.societe,
                                      fuseau_horaire=fuseau)

    def test_repli_profil_societe_avec_provenance(self):
        self._profil()

        effectif = fuseau_du_site({}, company=self.societe)
        self.assertEqual(effectif['fuseau'], 'Africa/Casablanca')
        self.assertEqual(effectif['provenance'], PROVENANCE_PROFIL_SOCIETE)
        self.assertEqual(effectif['mention'], MENTION_FUSEAU_PROFIL)

        blocs = _simuler(self.societe)
        heure = blocs['meteo']['heure']
        self.assertEqual(heure['fuseau_site'], 'Africa/Casablanca')
        self.assertEqual(heure['provenance_fuseau'],
                         PROVENANCE_PROFIL_SOCIETE)
        for nom in ('autoconsommation', 'batterie', 'hors_reseau'):
            self.assertNotEqual(
                (blocs[nom] or {}).get('motif_absence'), MOTIF_FUSEAU_ABSENT,
                nom)

    def test_imagerie_prime(self):
        self._profil('Africa/Casablanca')

        effectif = fuseau_du_site({'fuseau': 'Europe/Paris'},
                                  company=self.societe)
        self.assertEqual(effectif['fuseau'], 'Europe/Paris')
        self.assertEqual(effectif['provenance'], PROVENANCE_IMAGERIE)

        reglages = copy.deepcopy(REGLAGES)
        reglages['imagerie'] = {'fuseau': 'Europe/Paris'}
        heure = _simuler(self.societe, reglages)['meteo']['heure']
        self.assertEqual(heure['fuseau_site'], 'Europe/Paris')
        self.assertEqual(heure['provenance_fuseau'], PROVENANCE_IMAGERIE)

    def test_jamais_derive_de_la_longitude(self):
        # Ni imagerie, ni profil : aucun fuseau — l'épingle (lon −7,59) ne
        # sert jamais à en deviner un.
        effectif = fuseau_du_site({}, company=self.societe)
        self.assertIsNone(effectif['fuseau'])
        self.assertIsNone(effectif['provenance'])

        blocs = _simuler(self.societe)
        self.assertIsNone(blocs['meteo']['heure']['fuseau_site'])
        self.assertIsNone(blocs['meteo']['heure']['provenance_fuseau'])
        self.assertTrue(blocs['autoconsommation']['motif_absence'])

    def test_get_parametres_sert_site_effectif(self):
        self._profil()
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = get_user_model().objects.create_user(
            username='acal129', password='x', company=self.societe,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')

        reponse = api.get(URL_PARAMETRES)

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        effectif = reponse.data['imagerie']['site_effectif']
        self.assertEqual(effectif, {
            'fuseau': 'Africa/Casablanca',
            'source': PROVENANCE_PROFIL_SOCIETE,
            'mention': MENTION_FUSEAU_PROFIL})
