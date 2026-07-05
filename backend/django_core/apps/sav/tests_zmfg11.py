"""ZMFG11 — Prochaine défaillance estimée + prochain entretien dû sur la
fiche équipement (parité MTBF/Next Failure Odoo).

Couvre :
  * `prochaine_defaillance_estimee` = dernier correctif + MTBF, exact sur
    fixtures datées ;
  * absente (None) si moins de 2 tickets correctifs (MTBF indéfini) —
    jamais de division par zéro ;
  * `prochain_entretien_du` dérivé du `ContratMaintenance` ACTIF couvrant
    l'équipement (XCTR2) ;
  * absente si aucun contrat ne couvre l'équipement et aucun seuil compteur ;
  * exposée sur l'endpoint `equipements/{id}/estimations-maintenance/`.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zmfg11 -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import ContratMaintenance, Equipement, Ticket
from apps.sav.selectors import estimations_maintenance

User = get_user_model()


def make_company(slug='sav-zmfg11', nom='Sav Co ZMFG11'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZMFG11EstimationsMaintenanceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zmfg11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ZMFG11',
            email='zmfg11-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-ZMFG11', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZMFG11', sku='OND-ZMFG11',
            prix_achat=Decimal('300'), prix_vente=Decimal('600'))
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)

    def _ticket(self, date_ouverture, date_resolution=None):
        return Ticket.objects.create(
            company=self.company,
            reference=f'SAV-ZMFG11-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            equipement=self.equip, type=Ticket.Type.CORRECTIF,
            statut=(Ticket.Statut.RESOLU if date_resolution
                    else Ticket.Statut.NOUVEAU),
            date_ouverture=date_ouverture, date_resolution=date_resolution,
            created_by=self.admin)

    def test_prochaine_defaillance_estimee_exacte(self):
        # Tickets ouverts à J0, J+10, J+30 -> écarts 10, 20 -> MTBF = 15 jours.
        # Dernier correctif ouvert le 2026-01-31 (J+30).
        from datetime import timedelta

        self._ticket(date(2026, 1, 1), date(2026, 1, 3))
        self._ticket(date(2026, 1, 11), date(2026, 1, 14))
        self._ticket(date(2026, 1, 31), date(2026, 2, 2))

        data = estimations_maintenance(self.equip)
        self.assertEqual(
            data['prochaine_defaillance_estimee'],
            date(2026, 1, 31) + timedelta(days=15))

    def test_absente_sans_deux_correctifs(self):
        self._ticket(date(2026, 1, 1), date(2026, 1, 3))
        data = estimations_maintenance(self.equip)
        self.assertIsNone(data['prochaine_defaillance_estimee'])

    def test_prochain_entretien_du_from_covering_contract(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1),
            periodicite='annuel', actif=True)
        contrat.equipements.add(self.equip)

        data = estimations_maintenance(self.equip)
        self.assertEqual(
            data['prochain_entretien_du'], contrat.prochaine_visite())

    def test_prochain_entretien_du_none_when_no_covering_contract(self):
        autre_equip_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='Client',
            email='zmfg11-autre@example.invalid')
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=autre_equip_client,
            date_debut=date(2026, 1, 1), periodicite='annuel', actif=True)
        contrat.equipements.add(self.equip)  # posé mais client différent

        data = estimations_maintenance(self.equip)
        self.assertIsNone(data['prochain_entretien_du'])

    def test_endpoint_exposes_both_fields(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=date(2026, 1, 1), periodicite='annuel', actif=True)
        # Contrat sans registre d'équipements = couvre tout le client (XCTR2).
        api = auth(self.admin)
        resp = api.get(
            f'/api/django/sav/equipements/{self.equip.id}/estimations-maintenance/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn('prochaine_defaillance_estimee', resp.data)
        self.assertEqual(
            resp.data['prochain_entretien_du'],
            contrat.prochaine_visite().isoformat())
