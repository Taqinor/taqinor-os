"""AFAC19 (C-AFAC-015, décision AFAC82 : parquer) — la pile « mandat de
prélèvement » n'est plus exposée : route API ``mandats-paiement`` retirée
(404), viewset et service sans appelant ``debiter_mandat_pour_facture``
retirés ; les modèles ``MandatPaiement`` / ``TentativeDebitMandat`` et leurs
lignes restent intacts (aucune migration destructive).

Test-du-test : ré-enregistrer la route ⇒ ``test_route_mandats_retiree``
repasse à 200.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_mandat_parque"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class MandatParqueTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC19 Co', slug='afac19-co')
        self.user = User.objects.create_user(
            username='afac19_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Mandat', prenom='AFAC19',
            email='afac19@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_route_mandats_retiree(self):
        from apps.ventes.models import MandatPaiement
        mandat = MandatPaiement.objects.create(
            company=self.company, client=self.client_obj,
            provider='noop', token='TOK-AFAC19',
            statut=MandatPaiement.Statut.ACTIF)
        avant = MandatPaiement.objects.count()
        r = self.api.get('/api/django/ventes/mandats-paiement/')
        self.assertEqual(r.status_code, 404)
        r = self.api.post(
            f'/api/django/ventes/mandats-paiement/{mandat.id}/revoquer/')
        self.assertEqual(r.status_code, 404)
        # CLAUSE PERSISTANCE — les données restent.
        self.assertEqual(MandatPaiement.objects.count(), avant)
        mandat.refresh_from_db()
        self.assertEqual(mandat.statut, MandatPaiement.Statut.ACTIF)

    def test_service_et_viewset_retires(self):
        from apps.ventes import services, views
        from apps.ventes.domain import encaissements
        for nom in ('debiter_mandat_pour_facture', 'mandat_actif_pour_client'):
            with self.subTest(nom=nom):
                self.assertFalse(hasattr(encaissements, nom))
                self.assertFalse(hasattr(services, nom))
        self.assertFalse(hasattr(views, 'MandatPaiementViewSet'))
