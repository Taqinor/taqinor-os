"""XCTR2 — Registre des équipements couverts par contrat.

Couvre :
  * M2M CRUD via l'API (ajout/retrait d'équipements couverts) ;
  * un équipement d'une autre société est refusé (400) ;
  * indicateur « couvert / non couvert » calculé sur le ticket ;
  * un contrat sans équipement enregistré couvre tout (comportement
    historique préservé, aucune régression).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xctr2 -v 2
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import ContratMaintenance, Equipement, Ticket

User = get_user_model()


def make_company(slug='sav-xctr2', nom='Sav Co XCTR2'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XCTR2RegistreEquipementsTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company(slug='sav-xctr2-other', nom='Autre Co')
        self.admin = User.objects.create_user(
            username='xctr2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XCTR2',
            email='xctr2-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XCTR2', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur XCTR2', sku='OND-XCTR2',
            prix_achat=300, prix_vente=600)
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        self.equip_autre_company = Equipement.objects.create(
            company=self.other_company, produit=self.produit,
            installation=self.inst, created_by=self.admin)
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            installation=self.inst, date_debut=date(2026, 1, 1), actif=True)

    def test_ajouter_equipement_couvert_via_api(self):
        api = auth(self.admin)
        resp = api.patch(
            f'/api/django/sav/contrats-maintenance/{self.contrat.pk}/',
            {'equipements': [self.equip.pk]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.contrat.refresh_from_db()
        self.assertEqual(
            list(self.contrat.equipements.values_list('pk', flat=True)),
            [self.equip.pk])

    def test_equipement_autre_company_refuse(self):
        api = auth(self.admin)
        resp = api.patch(
            f'/api/django/sav/contrats-maintenance/{self.contrat.pk}/',
            {'equipements': [self.equip_autre_company.pk]}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_contrat_sans_registre_couvre_tout(self):
        # Comportement historique : M2M vide = couvre tout (pas de régression).
        self.assertTrue(self.contrat.couvre_equipement(self.equip))

    def test_contrat_avec_registre_refuse_equipement_non_liste(self):
        autre_equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        self.contrat.equipements.add(self.equip)
        self.assertTrue(self.contrat.couvre_equipement(self.equip))
        self.assertFalse(self.contrat.couvre_equipement(autre_equip))

    def test_ticket_indicateur_couvert(self):
        self.contrat.equipements.add(self.equip)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR2-1',
            client=self.client_obj, installation=self.inst,
            equipement=self.equip, created_by=self.admin)
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ticket.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['equipement_couvert'])

    def test_ticket_indicateur_non_couvert(self):
        autre_equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        self.contrat.equipements.add(self.equip)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XCTR2-2',
            client=self.client_obj, installation=self.inst,
            equipement=autre_equip, created_by=self.admin)
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/{ticket.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['equipement_couvert'])

    def test_ticket_creation_avertissement_non_bloquant(self):
        """Créer un ticket sur un équipement non couvert n'échoue jamais
        (avertissement seulement, non bloquant) — trace une note chatter."""
        autre_equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)
        self.contrat.equipements.add(self.equip)
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.pk, 'installation': self.inst.pk,
            'equipement': autre_equip.pk, 'type': 'correctif',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        from apps.sav.models import TicketActivity
        notes = TicketActivity.objects.filter(
            ticket_id=resp.data['id'], kind=TicketActivity.Kind.NOTE)
        self.assertTrue(
            any('non' in (n.body or '').lower()
                and 'couvert' in (n.body or '').lower() for n in notes))
