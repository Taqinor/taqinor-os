"""AUD133 — Promesse de paiement : écriture ouverte à tout rôle authentifié
malgré le docstring, et date non bornée gelant les relances à volonté.

`PromessePaiementViewSet` annonçait « Écriture réservée aux rôles
responsable/admin », mais `get_permissions` renvoyait `[IsAnyRole()]` dans les
DEUX branches — donc pour `create`, seule action d'écriture exposée. Et rien ne
bornait `date_promise` : la valeur du corps était écrite telle quelle dans
`facture.exclu_relances_jusquau`, que `relance_reminders` exclut ensuite via
`exclu_relances_jusquau__gte=today`. N'importe quel commercial pouvait donc
geler définitivement la relance d'une facture avec une promesse au 31/12/2030.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, PromessePaiement

User = get_user_model()

URL = '/api/django/ventes/promesses-paiement/'


class TestAud133PromessePaiement(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='aud133-co', defaults={'nom': 'AUD133 Co'})[0]
        self.responsable = User.objects.create_user(
            username='aud133_resp', password='x', role_legacy='responsable',
            company=self.company)
        # Rôle commercial « limité » : lecture + quelques écritures métier, mais
        # PAS le palier responsable/admin.
        self.commercial = User.objects.create_user(
            username='aud133_com', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur AUD133',
            telephone='+212600000133')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD133-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('10000.00'),
            date_echeance=date.today() - timedelta(days=30))

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _corps(self, jours=15):
        return {
            'facture': self.facture.id,
            'montant_promis': '5000.00',
            'date_promise': (date.today() + timedelta(days=jours)).isoformat(),
        }

    def test_creation_par_un_role_commercial_est_refusee(self):
        resp = self._api(self.commercial).post(
            URL, self._corps(), format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(PromessePaiement.objects.exists())
        self.facture.refresh_from_db()
        self.assertIsNone(self.facture.exclu_relances_jusquau)

    def test_lecture_reste_ouverte_a_tout_role(self):
        """La branche LECTURE reste `IsAnyRole` — on ne durcit que l'écriture."""
        resp = self._api(self.commercial).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_date_promise_a_cinq_ans_est_refusee(self):
        resp = self._api(self.responsable).post(
            URL, self._corps(jours=365 * 5), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('date_promise', resp.data)
        self.assertFalse(PromessePaiement.objects.exists())
        self.facture.refresh_from_db()
        self.assertIsNone(self.facture.exclu_relances_jusquau)

    def test_date_promise_passee_est_refusee(self):
        resp = self._api(self.responsable).post(
            URL, self._corps(jours=-1), format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('date_promise', resp.data)

    def test_promesse_valide_est_creee_et_suspend_la_relance(self):
        corps = self._corps(jours=15)
        resp = self._api(self.responsable).post(URL, corps, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.facture.refresh_from_db()
        self.assertEqual(
            self.facture.exclu_relances_jusquau.isoformat(),
            corps['date_promise'])

    def test_le_plafond_est_exactement_le_dernier_jour_accepte(self):
        from apps.ventes.recouvrement import PROMESSE_HORIZON_JOURS_MAX
        resp = self._api(self.responsable).post(
            URL, self._corps(jours=PROMESSE_HORIZON_JOURS_MAX),
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp2 = self._api(self.responsable).post(
            URL, self._corps(jours=PROMESSE_HORIZON_JOURS_MAX + 1),
            format='json')
        self.assertEqual(resp2.status_code, 400, resp2.data)
