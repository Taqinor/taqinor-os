"""NTDATA24 — consultation & rafraîchissement des golden records.

Couvre :
  * le critère d'acceptation : MODIFIER une source puis `consolider` met à
    jour l'attribut golden SANS toucher les sources ;
  * la lecture `/dataquality/golden-records/` (+ filtre `?entite=`) ;
  * le recalcul à la demande est idempotent ;
  * le job Beat hebdomadaire `consolider_golden_records` (fan-out sociétés
    actives) ;
  * une entité inconnue est refusée en français ;
  * le scoping société + le refus d'un utilisateur non responsable.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.dataquality import services
from apps.dataquality.models import GoldenRecord
from apps.dataquality.views import GoldenRecordViewSet
from authentication.models import Company

User = get_user_model()
CLIENT = GoldenRecord.Entite.CLIENT


class GoldenRecordApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA24 SA',
                                             slug='ntdata24-sa')
        cls.autre = Company.objects.create(nom='NTDATA24 Autre',
                                           slug='ntdata24-autre')
        cls.responsable = User.objects.create_user(
            username='ntdata24_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata24_simple', password='x', company=cls.company,
            role_legacy='normal')

    def _deux_clients(self, company=None):
        company = company or self.company
        premier = Client.objects.create(
            company=company, nom='Atlas Energie', ice='001234567000089',
            telephone='0600000001')
        second = Client.objects.create(
            company=company, nom='ATLAS ENERGIE SARL',
            ice='001234567000089', email='contact@atlas.ma')
        return premier, second

    def _appel(self, methode, chemin, vue, user=None, data=None, **kwargs):
        fabrique = APIRequestFactory()
        requete = getattr(fabrique, methode)(chemin, data, format='json')
        force_authenticate(requete, user=user or self.responsable)
        return vue(requete, **kwargs)

    def test_modifier_une_source_puis_consolider(self):
        """Critère : l'attribut golden suit la source, la source ne bouge pas."""
        premier, second = self._deux_clients()
        self._appel(
            'post', '/api/django/dataquality/golden-records/consolider/',
            GoldenRecordViewSet.as_view({'post': 'consolider'}))
        golden = GoldenRecord.objects.get(company=self.company,
                                          entite=CLIENT)
        self.assertEqual(golden.attributs['email']['valeur'],
                         'contact@atlas.ma')

        # La source change…
        second.email = 'direction@atlas.ma'
        second.save(update_fields=['email'])
        reponse = self._appel(
            'post', '/api/django/dataquality/golden-records/consolider/',
            GoldenRecordViewSet.as_view({'post': 'consolider'}))
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)

        golden.refresh_from_db()
        self.assertEqual(golden.attributs['email']['valeur'],
                         'direction@atlas.ma')
        # …et AUCUNE source n'a été touchée par la consolidation.
        premier.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(premier.nom, 'Atlas Energie')
        self.assertEqual(premier.email or '', '')
        self.assertEqual(second.nom, 'ATLAS ENERGIE SARL')
        self.assertEqual(second.email, 'direction@atlas.ma')

    def test_consolider_est_idempotent(self):
        self._deux_clients()
        vue = GoldenRecordViewSet.as_view({'post': 'consolider'})
        self._appel('post', '/api/django/dataquality/golden-records/consolider/',
                    vue)
        self._appel('post', '/api/django/dataquality/golden-records/consolider/',
                    vue)
        self.assertEqual(
            GoldenRecord.objects.filter(company=self.company).count(), 1)

    def test_lecture_et_filtre_entite(self):
        self._deux_clients()
        services.consolider_golden(self.company, CLIENT)
        liste = self._appel(
            'get', '/api/django/dataquality/golden-records/?entite=client',
            GoldenRecordViewSet.as_view({'get': 'list'}))
        self.assertEqual(liste.status_code, status.HTTP_200_OK)

        vide = self._appel(
            'get', '/api/django/dataquality/golden-records/?entite=produit',
            GoldenRecordViewSet.as_view({'get': 'list'}))
        self.assertEqual(vide.status_code, status.HTTP_200_OK)

    def test_entite_inconnue_refusee(self):
        reponse = self._appel(
            'post',
            '/api/django/dataquality/golden-records/consolider/?entite=licorne',
            GoldenRecordViewSet.as_view({'post': 'consolider'}))
        self.assertEqual(reponse.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('licorne', reponse.data['entite'])

    def test_scoping_societe(self):
        self._deux_clients(company=self.autre)
        services.consolider_golden(self.autre, CLIENT)
        liste = self._appel(
            'get', '/api/django/dataquality/golden-records/',
            GoldenRecordViewSet.as_view({'get': 'list'}))
        self.assertEqual(liste.status_code, status.HTTP_200_OK)
        resultats = liste.data.get('results', liste.data)
        self.assertEqual(len(resultats), 0)

    def test_utilisateur_non_responsable_refuse(self):
        reponse = self._appel(
            'get', '/api/django/dataquality/golden-records/',
            GoldenRecordViewSet.as_view({'get': 'list'}), user=self.simple)
        self.assertEqual(reponse.status_code, status.HTTP_403_FORBIDDEN)


class ConsoliderGoldenRecordsJobTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA24 Job',
                                             slug='ntdata24-job')
        Client.objects.create(company=cls.company, nom='Atlas Energie',
                              ice='001234567000089', telephone='0600000001')
        Client.objects.create(company=cls.company, nom='ATLAS ENERGIE SARL',
                              ice='001234567000089',
                              email='contact@atlas.ma')

    def test_job_hebdomadaire_consolide_chaque_societe(self):
        from apps.dataquality.tasks import consolider_golden_records

        recap = consolider_golden_records()
        ligne = next(r for r in recap if r['company'] == self.company.pk)
        self.assertEqual(ligne['nb_golden'], 1)
        self.assertEqual(
            GoldenRecord.objects.filter(company=self.company).count(), 1)
