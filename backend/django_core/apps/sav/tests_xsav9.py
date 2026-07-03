"""XSAV9 — Affectation automatique des tickets (round-robin / équilibrage).

Couvre :
  * OFF par défaut → aucun technicien affecté automatiquement (inchangé) ;
  * ON, sans technicien fourni → le technicien le MOINS chargé est choisi ;
  * répartition équilibrée démontrée sur plusieurs créations successives ;
  * un technicien explicitement fourni n'est jamais écrasé ;
  * migration additive (défaut False).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav9 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import SavSlaSettings, Ticket
from apps.sav.services import assign_technicien_auto

User = get_user_model()


def make_company(slug='sav-xsav9', nom='Sav Co XSAV9'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV9AffectationAutoTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.tech_a = User.objects.create_user(
            username='xsav9_tech_a', password='x', role_legacy='normal',
            company=self.company)
        self.tech_b = User.objects.create_user(
            username='xsav9_tech_b', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav9-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV9', client=self.client_obj)

        # Les deux techniciens participent au pool (déjà assignés une fois).
        Ticket.objects.create(
            company=self.company, reference='SAV-XSAV9-SEED-A',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.CLOTURE,
            technicien_responsable=self.tech_a, created_by=self.admin)
        Ticket.objects.create(
            company=self.company, reference='SAV-XSAV9-SEED-B',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.CLOTURE,
            technicien_responsable=self.tech_b, created_by=self.admin)

    def test_off_par_defaut_aucune_affectation(self):
        sla = SavSlaSettings.get(self.company)
        self.assertFalse(sla.affectation_auto_sav)
        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(resp.data['technicien_responsable'])

    def test_on_affecte_le_technicien_le_moins_charge(self):
        sla = SavSlaSettings.get(self.company)
        sla.affectation_auto_sav = True
        sla.save(update_fields=['affectation_auto_sav'])

        # tech_a a un ticket OUVERT en plus → tech_b est moins chargé.
        Ticket.objects.create(
            company=self.company, reference='SAV-XSAV9-OPEN-A',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=Ticket.Statut.NOUVEAU,
            technicien_responsable=self.tech_a, created_by=self.admin)

        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['technicien_responsable'], self.tech_b.id)

    def test_on_ne_remplace_pas_un_technicien_explicite(self):
        sla = SavSlaSettings.get(self.company)
        sla.affectation_auto_sav = True
        sla.save(update_fields=['affectation_auto_sav'])

        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'technicien_responsable': self.tech_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['technicien_responsable'], self.tech_a.id)

    def test_repartition_equilibree_sur_plusieurs_creations(self):
        sla = SavSlaSettings.get(self.company)
        sla.affectation_auto_sav = True
        sla.save(update_fields=['affectation_auto_sav'])

        chosen = []
        for i in range(4):
            resp = self.api.post('/api/django/sav/tickets/', {
                'client': self.client_obj.id, 'installation': self.inst.id,
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.content)
            chosen.append(resp.data['technicien_responsable'])
        # Chaque technicien reçoit exactement 2 des 4 nouveaux tickets
        # (équilibrage strict : le moins chargé est toujours repris).
        self.assertEqual(chosen.count(self.tech_a.id), 2)
        self.assertEqual(chosen.count(self.tech_b.id), 2)

    def test_technicien_indisponible_jamais_choisi(self):
        """Sans dossier RH pour tech_a, le repli sûr le considère disponible ;
        on simule l'indisponibilité directement via le service pour vérifier
        que le pool exclut bien un technicien marqué indisponible."""
        from unittest import mock

        with mock.patch(
                'apps.sav.services._technicien_indisponible',
                side_effect=lambda company, user, jour: user.id == self.tech_b.id):
            chosen = assign_technicien_auto(company=self.company)
        self.assertEqual(chosen.id, self.tech_a.id)

    def test_migration_defaut_off(self):
        other = make_company(slug='sav-xsav9-other', nom='Sav Co XSAV9 Other')
        sla = SavSlaSettings.get(other)
        self.assertFalse(sla.affectation_auto_sav)

    def test_aucun_candidat_renvoie_none(self):
        empty_company = make_company(slug='sav-xsav9-empty', nom='Sav Co XSAV9 Empty')
        result = assign_technicien_auto(company=empty_company)
        self.assertIsNone(result)
