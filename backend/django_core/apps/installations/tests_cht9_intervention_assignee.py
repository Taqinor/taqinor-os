"""CHT9 — Notifier le technicien affecté/réaffecté à une intervention.

Avant CHT9, affecter (création) ou réaffecter (édition, garde YHIRE9) un
technicien à une intervention ne le notifiait JAMAIS : aucun EventType dédié
n'existait, et les trois sites qui empruntaient ``CHANTIER_DUE`` par facilité
(réassignation en masse, annulation, tranche à facturer) ne couvraient pas ce
cas. Ce module couvre le nouveau ``_notifier_intervention_assignee``
(``INTERVENTION_ASSIGNEE``), câblé depuis ``InterventionViewSet.perform_
create``/``perform_update`` via ``transaction.on_commit`` (QJR4-05 — patron de
capture ``tests_qjr422_notifications_on_commit.py``).

Run :
    python manage.py test apps.installations.tests_cht9_intervention_assignee -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.notifications.models import EventType, Notification
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht9-co-{n}', defaults={'nom': nom or f'CHT9 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'cht9-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'cht9-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CHT9-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestAffectationALaCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech = make_user(self.company, username='cht9-tech-1')

    def test_technicien_affecte_est_notifie(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api.post(f'{BASE}/interventions/', {
                'installation': self.inst.id,
                'type_intervention': Intervention.Type.CONTROLE,
                'technicien': self.tech.id,
            })
        self.assertEqual(r.status_code, 201, r.data)
        notif = Notification.objects.get(
            recipient=self.tech, event_type=EventType.INTERVENTION_ASSIGNEE)
        self.assertEqual(
            notif.link, f'/interventions?id={r.data["id"]}')
        self.assertEqual(notif.company_id, self.company.id)

    def test_sans_technicien_aucune_notification(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api.post(f'{BASE}/interventions/', {
                'installation': self.inst.id,
                'type_intervention': Intervention.Type.CONTROLE,
            })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.INTERVENTION_ASSIGNEE).exists())


class TestReaffectationALaModification(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.inst = make_chantier(self.company, self.admin)
        self.tech_initial = make_user(self.company, username='cht9-tech-init')
        self.tech_nouveau = make_user(self.company, username='cht9-tech-new')
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention=Intervention.Type.CONTROLE,
            technicien=self.tech_initial, created_by=self.admin)

    def test_changement_de_technicien_notifie_le_nouveau(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api.patch(f'{BASE}/interventions/{self.interv.id}/', {
                'technicien': self.tech_nouveau.id,
            }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        notif = Notification.objects.get(
            recipient=self.tech_nouveau,
            event_type=EventType.INTERVENTION_ASSIGNEE)
        self.assertEqual(notif.link, f'/interventions?id={self.interv.id}')
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.tech_initial,
                event_type=EventType.INTERVENTION_ASSIGNEE).exists())

    def test_edition_sans_changer_le_technicien_ne_notifie_personne(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.api.patch(f'{BASE}/interventions/{self.interv.id}/', {
                'priorite': Intervention.Priorite.HAUTE,
            }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(
            Notification.objects.filter(
                event_type=EventType.INTERVENTION_ASSIGNEE).exists())
