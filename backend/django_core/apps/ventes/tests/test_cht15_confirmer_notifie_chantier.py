"""CHT15 — la confirmation d'un BC notifie le responsable du chantier.

``BonCommandeViewSet.confirmer`` réservait déjà le stock (YDOCF7) mais ne
notifiait JAMAIS le chantier né du même devis que le matériel est commandé.
Ce module couvre le nouveau nudge ``EventType.CHANTIER_MATERIEL_CONFIRME``
(notification SEULEMENT — aucune transition de statut chantier).

Run :
    python manage.py test apps.ventes.tests.test_cht15_confirmer_notifie_chantier -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.notifications.models import EventType, Notification
from apps.ventes.models import BonCommande, Devis
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/ventes'


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht15c-co-{n}', defaults={'nom': nom or f'CHT15C Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'cht15c-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CHT15C',
        email=f'cht15c-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CHT15C-{n}', client=client,
        statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))


class TestConfirmerNotifieResponsableChantier(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.responsable = make_user(
            self.company, username='cht15c-responsable-chantier')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-CHT15C-1',
            client=self.client_obj, devis=self.devis,
            technicien_responsable=self.responsable)
        self.bc = BonCommande.objects.create(
            company=self.company, reference='BC-CHT15C-1',
            client=self.client_obj, devis=self.devis,
            statut=BonCommande.Statut.EN_ATTENTE)

    def test_confirmation_notifie_le_bon_responsable(self):
        r = self.api.post(f'{BASE}/bons-commande/{self.bc.id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        notif = Notification.objects.get(
            recipient=self.responsable,
            event_type=EventType.CHANTIER_MATERIEL_CONFIRME)
        self.assertEqual(notif.link, f'/chantiers?id={self.inst.id}')
        self.assertIn(self.bc.reference, notif.body)

    def test_bc_sans_devis_ne_notifie_personne(self):
        bc_manuel = BonCommande.objects.create(
            company=self.company, reference='BC-CHT15C-2',
            client=self.client_obj, statut=BonCommande.Statut.EN_ATTENTE)
        r = self.api.post(f'{BASE}/bons-commande/{bc_manuel.id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.CHANTIER_MATERIEL_CONFIRME).exists())

    def test_chantier_sans_technicien_ne_notifie_personne(self):
        self.inst.technicien_responsable = None
        self.inst.save(update_fields=['technicien_responsable'])
        r = self.api.post(f'{BASE}/bons-commande/{self.bc.id}/confirmer/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.CHANTIER_MATERIEL_CONFIRME).exists())

    def test_confirmation_ne_change_aucun_statut_chantier(self):
        statut_avant = self.inst.statut
        self.api.post(f'{BASE}/bons-commande/{self.bc.id}/confirmer/')
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, statut_avant)
