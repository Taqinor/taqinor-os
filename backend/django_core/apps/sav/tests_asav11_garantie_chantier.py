"""ASAV11 (D-ASAV-2) — un ticket sans équipement sur un chantier récemment
réceptionné (garantie légale réception + 12 mois, ou garantie de pose) n'est
plus « facturable » d'office : couverture « à déterminer », ``facturer`` 409.

Run :
    python manage.py test apps.sav.tests_asav11_garantie_chantier -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.dateutils import add_months
from apps.sav.models import Equipement, Ticket
from apps.stock.models import Produit

User = get_user_model()


class GarantieChantierTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav11-co', defaults={'nom': 'ASAV11 Co'})
        self.user = User.objects.create_user(
            username='asav11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV11')
        self.today = timezone.localdate()

    def _chantier(self, ref, mois_reception, pose=None):
        return Installation.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            date_reception=add_months(self.today, -mois_reception),
            garantie_installation_mois=pose)

    def _ticket(self, ref, chantier, **kw):
        return Ticket.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            installation=chantier, type=Ticket.Type.CORRECTIF,
            created_by=self.user, date_ouverture=self.today, **kw)

    def test_chantier_recent_pas_facturable(self):
        ticket = self._ticket('SAV-A11-1', self._chantier('CHT-A11-1', 3, 24))
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.A_DETERMINER)
        r = self.api.post(f'/api/django/sav/tickets/{ticket.pk}/facturer/',
                          {}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.facture_id_ext)

    def test_pose_plus_longue_que_legale(self):
        # Réceptionné il y a 18 mois, garantie de pose 24 mois : encore couvert.
        ticket = self._ticket('SAV-A11-2', self._chantier('CHT-A11-2', 18, 24))
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.A_DETERMINER)

    def test_chantier_ancien_facturable(self):
        ticket = self._ticket('SAV-A11-3', self._chantier('CHT-A11-3', 30))
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.FACTURABLE)

    def test_equipement_prime(self):
        chantier = self._chantier('CHT-A11-4', 3, 24)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-A11',
            prix_achat=0, prix_vente=Decimal('1000'))
        eq = Equipement.objects.create(
            company=self.company, produit=produit, installation=chantier,
            numero_serie='A11-SN', date_pose=add_months(self.today, -30))
        eq.recompute_garanties()
        eq.save(update_fields=['date_fin_garantie',
                               'date_fin_garantie_production'])
        ticket = self._ticket('SAV-A11-4', chantier, equipement=eq)
        self.assertEqual(ticket.couverture_calculee(),
                         Ticket.Couverture.FACTURABLE)
