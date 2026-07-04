"""XSAV17 — Relevés compteur (heures / kWh) + entretien conditionnel.

Couvre :
  * un relevé décroissant est refusé ;
  * franchissement du seuil -> exactement 1 ticket préventif généré ;
  * un second relevé au-dessus du même seuil (avant reset) n'en recrée pas un
    second (idempotence) ;
  * sans seuil configuré, aucun ticket n'est jamais généré (comportement OFF
    par défaut inchangé).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav17 -v 2
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
from apps.sav.models import Equipement, Ticket
from apps.sav.services import ReleveDecroissantError, enregistrer_releve_compteur

User = get_user_model()


def make_company(slug='sav-xsav17', nom='Sav Co XSAV17'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV17ReleveCompteurTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav17_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav17-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV17', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Pompe X', sku='POMPE-X-XSAV17',
            prix_achat=300, prix_vente=600)

    def _equip(self, seuil=None):
        return Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            entretien_toutes_les_heures=seuil, created_by=self.admin)

    def test_releve_decroissant_refuse(self):
        equip = self._equip()
        enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('100'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        with self.assertRaises(ReleveDecroissantError):
            enregistrer_releve_compteur(
                company=self.company, equipement=equip, type_releve='heures',
                valeur=Decimal('90'), date_releve=date(2026, 1, 2),
                created_by=self.admin)

    def test_franchissement_seuil_genere_exactement_un_ticket(self):
        equip = self._equip(seuil=Decimal('500'))
        _, ticket = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('600'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket.type, Ticket.Type.PREVENTIF)
        self.assertEqual(
            Ticket.objects.filter(equipement=equip).count(), 1)

    def test_sans_seuil_franchissement_jamais(self):
        equip = self._equip(seuil=None)
        _, ticket = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('10000'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        self.assertIsNone(ticket)
        self.assertEqual(Ticket.objects.filter(equipement=equip).count(), 0)

    def test_sous_seuil_aucun_ticket(self):
        equip = self._equip(seuil=Decimal('500'))
        _, ticket = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('200'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        self.assertIsNone(ticket)

    def test_idempotent_pas_de_second_ticket_avant_reset(self):
        equip = self._equip(seuil=Decimal('500'))
        _, ticket1 = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('600'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        self.assertIsNotNone(ticket1)
        # Second relevé toujours au-dessus de la référence mise à jour
        # (600) mais n'ayant PAS encore franchi un nouveau seuil de 500.
        _, ticket2 = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('900'), date_releve=date(2026, 1, 5),
            created_by=self.admin)
        self.assertIsNone(ticket2)
        self.assertEqual(Ticket.objects.filter(equipement=equip).count(), 1)

    def test_nouveau_franchissement_apres_reset_genere_second_ticket(self):
        equip = self._equip(seuil=Decimal('500'))
        enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('600'), date_releve=date(2026, 1, 1),
            created_by=self.admin)
        _, ticket2 = enregistrer_releve_compteur(
            company=self.company, equipement=equip, type_releve='heures',
            valeur=Decimal('1150'), date_releve=date(2026, 2, 1),
            created_by=self.admin)
        self.assertIsNotNone(ticket2)
        self.assertEqual(Ticket.objects.filter(equipement=equip).count(), 2)

    # ── API ──────────────────────────────────────────────────────────────────

    def test_api_enregistre_releve_et_genere_ticket(self):
        equip = self._equip(seuil=Decimal('500'))
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/equipements/{equip.id}/releves-compteur/',
            {'type': 'heures', 'valeur': '600', 'date': '2026-01-01'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNotNone(resp.data['ticket_genere'])

    def test_api_releve_decroissant_400(self):
        equip = self._equip()
        api = auth(self.admin)
        api.post(
            f'/api/django/sav/equipements/{equip.id}/releves-compteur/',
            {'type': 'heures', 'valeur': '100', 'date': '2026-01-01'})
        resp = api.post(
            f'/api/django/sav/equipements/{equip.id}/releves-compteur/',
            {'type': 'heures', 'valeur': '50', 'date': '2026-01-02'})
        self.assertEqual(resp.status_code, 400, resp.content)
