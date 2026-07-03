"""XSAV13 — Garantie légale de conformité (loi 31-08).

Couvre :
  * équipement de 8 mois sans garantie constructeur = sous garantie (légale) ;
  * date_fin_garantie_legale = date_pose + 12 mois, calculée (pas stockée) ;
  * date_fin_garantie_effective = MAX(légale, commerciale) ;
  * Ticket.sous_garantie_calcule reflète la garantie légale seule ;
  * mention PDF « Garantie légale de conformité — loi 31-08 » quand elle
    s'applique seule ;
  * filtre « legale_uniquement » sur le registre des équipements.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav13 -v 2
"""
from datetime import date, timedelta
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
from apps.sav.pdf import rapport_intervention_pdf

User = get_user_model()


def make_company(slug='sav-xsav13', nom='Sav Co XSAV13'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV13GarantieLegaleTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav13_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav13-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV13', client=self.client_obj)
        # Produit SANS garantie constructeur — seule la loi 31-08 s'applique.
        self.produit_sans_garantie = Produit.objects.create(
            company=self.company, nom='Panneau Y', sku='PAN-Y-XSAV13',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'))

    def _equip(self, produit, date_pose):
        e = Equipement.objects.create(
            company=self.company, produit=produit, installation=self.inst,
            date_pose=date_pose, created_by=self.user)
        e.recompute_garanties()
        e.save()
        return e

    def test_8_mois_sans_garantie_constructeur_sous_garantie_legale(self):
        date_pose = date.today() - timedelta(days=8 * 30)
        equip = self._equip(self.produit_sans_garantie, date_pose)
        self.assertIsNone(equip.date_fin_garantie)  # pas de garantie constructeur.
        self.assertIsNotNone(equip.date_fin_garantie_legale)
        self.assertTrue(equip.sous_garantie_legale_seule)
        self.assertIsNotNone(equip.date_fin_garantie_effective)

    def test_13_mois_hors_garantie_legale_et_commerciale(self):
        date_pose = date.today() - timedelta(days=13 * 30)
        equip = self._equip(self.produit_sans_garantie, date_pose)
        self.assertFalse(equip.sous_garantie_legale_seule)
        today = date.today()
        self.assertLess(equip.date_fin_garantie_effective, today)

    def test_date_fin_garantie_legale_12_mois(self):
        equip = self._equip(self.produit_sans_garantie, date(2024, 1, 15))
        self.assertEqual(equip.date_fin_garantie_legale, date(2025, 1, 15))

    def test_effective_est_max_legale_commerciale(self):
        produit_24m = Produit.objects.create(
            company=self.company, nom='Onduleur Z', sku='OND-Z-XSAV13',
            prix_achat=Decimal('500'), prix_vente=Decimal('900'),
            garantie_mois=24)
        equip = self._equip(produit_24m, date(2024, 1, 15))
        # Commerciale (24 m) > légale (12 m) → effective = commerciale.
        self.assertEqual(equip.date_fin_garantie, date(2026, 1, 15))
        self.assertEqual(equip.date_fin_garantie_legale, date(2025, 1, 15))
        self.assertEqual(equip.date_fin_garantie_effective, date(2026, 1, 15))
        self.assertFalse(equip.sous_garantie_legale_seule)

    def test_ticket_sous_garantie_calcule_reflete_legale(self):
        date_pose = date.today() - timedelta(days=8 * 30)
        equip = self._equip(self.produit_sans_garantie, date_pose)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV13-1',
            client=self.client_obj, installation=self.inst,
            equipement=equip, type=Ticket.Type.CORRECTIF,
            created_by=self.user)
        self.assertEqual(ticket.sous_garantie_calcule, Ticket.SousGarantie.OUI)

    def test_mention_pdf_garantie_legale_seule(self):
        date_pose = date.today() - timedelta(days=8 * 30)
        equip = self._equip(self.produit_sans_garantie, date_pose)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV13-2',
            client=self.client_obj, installation=self.inst,
            equipement=equip, type=Ticket.Type.CORRECTIF,
            created_by=self.user)
        pdf_bytes = rapport_intervention_pdf(ticket)
        self.assertGreater(len(pdf_bytes), 0)

    def test_filtre_legale_uniquement_registre(self):
        date_pose_legale = date.today() - timedelta(days=8 * 30)
        equip_legale = self._equip(self.produit_sans_garantie, date_pose_legale)

        produit_24m = Produit.objects.create(
            company=self.company, nom='Onduleur W', sku='OND-W-XSAV13',
            prix_achat=Decimal('500'), prix_vente=Decimal('900'),
            garantie_mois=24)
        self._equip(produit_24m, date(2024, 1, 15))  # sous garantie commerciale.

        resp = self.api.get(
            '/api/django/sav/equipements/', {'garantie': 'legale_uniquement'})
        self.assertEqual(resp.status_code, 200, resp.content)
        ids = [row['id'] for row in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])]
        self.assertIn(equip_legale.id, ids)
