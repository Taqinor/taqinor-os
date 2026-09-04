"""AUD609 — deux DELETE légaux qui n'étaient gardés par rien.

* ``DossierAOViewSet`` n'avait AUCUNE garde de statut : un simple DELETE HTTP
  effaçait un dossier au statut ``DEPOSE`` — le pli est chez l'acheteur — ou
  ``CLOS``, avec ses pièces, ses artefacts et sa piste de contrôle. La machine
  d'états dit pourtant déjà que ``DEPOSE`` ne mène qu'à ``CLOS`` : « l'histoire
  d'un pli remis ne se réécrit pas ».
* ``CautionSoumissionViewSet`` non plus : une caution ``APPELÉE`` — la banque a
  DÉJÀ débité le montant — s'effaçait comme une ligne de brouillon.

Run :
    python manage.py test apps.ao.tests.test_aud609_delete_garde -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre, CautionSoumission, DossierAO
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ao/'


class BaseSuppression(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD609 AO',
                                              slug='aud609-ao')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-609-1', objet='Suppression')
        role = Role.objects.create(company=self.company, nom='AUD609 gestion',
                                   permissions=[AO_VOIR, AO_GERER])
        self.user = User.objects.create_user(
            username='aud609', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _dossier(self, statut):
        dossier = DossierAO.objects.create(
            company=self.company, appel_offre=self.ao,
            reference=f'AODOS-609-{statut}')
        # `DocumentMetier` garde la mutation du statut : on pose l'état de
        # DÉPART par `update()`, qui contourne `save()` par construction.
        DossierAO.objects.filter(pk=dossier.pk).update(statut=statut)
        dossier.refresh_from_db()
        return dossier


class TestDossierDepose(BaseSuppression):
    def test_un_dossier_depose_ne_se_supprime_pas(self):
        dossier = self._dossier(DossierAO.Statut.DEPOSE)
        reponse = self.api.delete(f'{BASE}dossiers-ao/{dossier.pk}/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertTrue(DossierAO.objects.filter(pk=dossier.pk).exists())

    def test_un_dossier_clos_ne_se_supprime_pas(self):
        dossier = self._dossier(DossierAO.Statut.CLOS)
        reponse = self.api.delete(f'{BASE}dossiers-ao/{dossier.pk}/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertTrue(DossierAO.objects.filter(pk=dossier.pk).exists())

    def test_un_dossier_en_montage_reste_supprimable(self):
        """Fermer la fuite ne doit pas geler un brouillon."""
        dossier = self._dossier(DossierAO.Statut.MONTAGE)
        reponse = self.api.delete(f'{BASE}dossiers-ao/{dossier.pk}/')
        self.assertEqual(reponse.status_code, 204, reponse.data)
        self.assertFalse(DossierAO.objects.filter(pk=dossier.pk).exists())

    def test_le_refus_NOMME_le_statut(self):
        dossier = self._dossier(DossierAO.Statut.DEPOSE)
        reponse = self.api.delete(f'{BASE}dossiers-ao/{dossier.pk}/')
        self.assertIn('Déposé', str(reponse.data))


class TestCautionAppelee(BaseSuppression):
    def _caution(self, statut):
        caution = CautionSoumission.objects.create(
            company=self.company, appel_offre=self.ao,
            montant=Decimal('50000.00'))
        CautionSoumission.objects.filter(pk=caution.pk).update(statut=statut)
        caution.refresh_from_db()
        return caution

    def test_une_caution_appelee_ne_se_supprime_pas(self):
        caution = self._caution(CautionSoumission.Statut.APPELEE)
        reponse = self.api.delete(f'{BASE}cautions-soumission/{caution.pk}/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertTrue(
            CautionSoumission.objects.filter(pk=caution.pk).exists())

    def test_une_caution_constituee_reste_supprimable(self):
        caution = self._caution(CautionSoumission.Statut.CONSTITUEE)
        reponse = self.api.delete(f'{BASE}cautions-soumission/{caution.pk}/')
        self.assertEqual(reponse.status_code, 204, reponse.data)

    def test_une_caution_restituee_reste_supprimable(self):
        """Restituée = la garantie est rendue, aucun débit à protéger."""
        caution = self._caution(CautionSoumission.Statut.RESTITUEE)
        reponse = self.api.delete(f'{BASE}cautions-soumission/{caution.pk}/')
        self.assertEqual(reponse.status_code, 204, reponse.data)
