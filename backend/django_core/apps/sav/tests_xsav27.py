"""XSAV27 — Prêt / échange anticipé d'équipement (loaner).

Couvre :
  * sortir un prêt décrémente le stock exactement une fois (SORTIE) ;
  * retourner un prêt réintègre le stock exactement une fois (ENTRÉE),
    idempotent (un second retour ne mouvemente rien de plus) ;
  * jamais de stock négatif (refuse si aucune unité disponible) ;
  * alerte de dépassement : `en_retard` correct + `services.prets_en_retard`
    remonte les prêts EN_COURS dont la date prévue est dépassée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav27 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import PretEquipement, Ticket
from apps.sav.services import (
    PretEquipementError, creer_pret_equipement, prets_en_retard,
    retourner_pret_equipement,
)
from apps.stock.models import Produit

User = get_user_model()


def make_company(slug='sav-xsav27', nom='Sav Co XSAV27'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV27PretEquipementServiceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav27_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav27-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV27', client=self.client_obj)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur Prêt', sku='OND-XSAV27',
            prix_achat=3000, prix_vente=6000, quantite_stock=2)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV27-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def test_sortie_decremente_le_stock_une_fois(self):
        pret = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-1', date_sortie=date.today(),
            date_retour_prevue=date.today() + timedelta(days=14),
            user=self.admin)
        self.assertTrue(pret.stock_sorti)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 1)

    def test_stock_insuffisant_refuse(self):
        self.onduleur.quantite_stock = 0
        self.onduleur.save(update_fields=['quantite_stock'])
        with self.assertRaises(PretEquipementError):
            creer_pret_equipement(
                company=self.company, ticket=self.ticket,
                produit=self.onduleur, numero_serie='SN-PRET-2',
                date_sortie=date.today(), date_retour_prevue=None,
                user=self.admin)

    def test_retour_reintegre_stock_une_seule_fois(self):
        pret = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-3', date_sortie=date.today(),
            date_retour_prevue=date.today() + timedelta(days=7),
            user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 1)

        retourner_pret_equipement(
            pret=pret, date_retour_reelle=date.today(), user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)

        # Idempotence : un second retour ne mouvemente rien de plus.
        pret.refresh_from_db()
        retourner_pret_equipement(
            pret=pret, date_retour_reelle=date.today(), user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)
        self.assertEqual(pret.statut, PretEquipement.Statut.RETOURNE)

    def test_alerte_depassement(self):
        pret_en_retard = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-4', date_sortie=date.today() - timedelta(days=30),
            date_retour_prevue=date.today() - timedelta(days=5),
            user=self.admin)
        self.assertTrue(pret_en_retard.en_retard)

        retards = prets_en_retard(self.company)
        self.assertIn(pret_en_retard.id, [p.id for p in retards])

        # Un prêt retourné n'est jamais en retard, même si la date prévue
        # est dépassée.
        retourner_pret_equipement(
            pret=pret_en_retard, date_retour_reelle=date.today(),
            user=self.admin)
        self.assertFalse(pret_en_retard.en_retard)

    def test_endpoint_sortie_et_retour(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/',
            {'produit': self.onduleur.id, 'numero_serie': 'SN-API-1',
             'date_retour_prevue': (date.today() + timedelta(days=10)).isoformat()})
        self.assertEqual(resp.status_code, 201, resp.content)
        pret_id = resp.data['id']

        resp = api.get(
            f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)

        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/'
            f'{pret_id}/retourner/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], PretEquipement.Statut.RETOURNE)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)
