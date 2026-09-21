"""NTCPQ25 — Rapport « Historique des approbations de remise »."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import EtapeApprobationDevis
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, DevisFactory, UserFactory

RAPPORT = '/api/django/cpq/rapports/approbations/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestRapportApprobations(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.approbateur_a = UserFactory(company=self.company)
        self.approbateur_b = UserFactory(company=self.company)
        self.devis = DevisFactory(
            company=self.company, remise_globale=Decimal('30'))

    def _etape(self, *, approbateur, statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
               heures_traitement=None, commentaire=''):
        etape = EtapeApprobationDevis.objects.create(
            company=self.company, devis=self.devis, niveau=1,
            approbateur=approbateur, statut=statut, commentaire=commentaire)
        if heures_traitement is not None:
            creation = timezone.now() - timedelta(hours=heures_traitement)
            decision = timezone.now()
            EtapeApprobationDevis.objects.filter(id=etape.id).update(
                date_creation=creation, decision_le=decision)
        return etape

    def test_liste_toutes_les_etapes(self):
        self._etape(approbateur=self.approbateur_a)
        self._etape(approbateur=self.approbateur_b)
        resp = auth(self.admin).get(RAPPORT)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lignes']), 2)

    def test_filtre_par_approbateur(self):
        self._etape(approbateur=self.approbateur_a)
        self._etape(approbateur=self.approbateur_b)
        resp = auth(self.admin).get(
            RAPPORT, {'approbateur_id': self.approbateur_a.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(
            resp.data['lignes'][0]['approbateur'], self.approbateur_a.username)

    def test_delai_de_traitement_calcule_en_heures(self):
        self._etape(
            approbateur=self.approbateur_a,
            statut=EtapeApprobationDevis.Statut.APPROUVE,
            heures_traitement=5)
        resp = auth(self.admin).get(RAPPORT)
        ligne = resp.data['lignes'][0]
        self.assertIsNotNone(ligne['delai_traitement_heures'])
        self.assertAlmostEqual(ligne['delai_traitement_heures'], 5, delta=0.05)

    def test_en_attente_delai_none(self):
        self._etape(approbateur=self.approbateur_a)
        resp = auth(self.admin).get(RAPPORT)
        self.assertIsNone(resp.data['lignes'][0]['delai_traitement_heures'])

    def test_motif_rejet_seulement_si_rejete(self):
        self._etape(
            approbateur=self.approbateur_a,
            statut=EtapeApprobationDevis.Statut.REJETE,
            commentaire='Remise trop forte')
        resp = auth(self.admin).get(RAPPORT)
        self.assertEqual(resp.data['lignes'][0]['motif_rejet'],
                         'Remise trop forte')

    def test_export_xlsx(self):
        self._etape(approbateur=self.approbateur_a)
        resp = auth(self.admin).get(RAPPORT, {'export': 'xlsx'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])

    def test_ecriture_reservee_staff(self):
        normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        resp = auth(normal).get(RAPPORT)
        self.assertEqual(resp.status_code, 403)
