"""VX214 — les kinds d'EXÉCUTION entrent dans « Ma file » (jamais une 2ᵉ
boîte). `MesActivitesPage`/`ApprobationsPage` n'agrégeaient que
`records.Activity`/les approbations — un chantier assigné, une intervention à
faire, une DA approuvée à commander, un ticket transféré n'apparaissaient dans
AUCUNE boîte. Ce test couvre les 4 kinds d'exécution + le scoping
company/user, via le MÊME endpoint `ma-file/` (VX83) — aucun nouvel
endpoint/écran.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def _company(name='VX214 Co'):
    return Company.objects.create(nom=name)


def _user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy)


def _client(company):
    from apps.crm.models import Client
    return Client.objects.create(
        company=company, nom='Client VX214',
        email=f'vx214-{company.id}@example.invalid')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Vx214ChantierAssigneTests(TestCase):

    def setUp(self):
        self.company = _company('VX214 Chantier Co')
        self.tech = _user(self.company, 'vx214_tech')
        self.other = _user(self.company, 'vx214_other')

    def test_chantier_assigne_visible_pour_son_technicien(self):
        from apps.installations.models import Installation
        Installation.objects.create(
            company=self.company, reference='CH-VX214-1',
            client=_client(self.company), technicien_responsable=self.tech,
            statut=Installation.Statut.EN_COURS)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertIn('chantier_assigne', kinds)

    def test_chantier_receptionne_n_apparait_plus(self):
        from apps.installations.models import Installation
        Installation.objects.create(
            company=self.company, reference='CH-VX214-2',
            client=_client(self.company), technicien_responsable=self.tech,
            statut=Installation.Statut.RECEPTIONNE)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('chantier_assigne', kinds)

    def test_chantier_invisible_pour_un_autre_technicien(self):
        from apps.installations.models import Installation
        Installation.objects.create(
            company=self.company, reference='CH-VX214-3',
            client=_client(self.company), technicien_responsable=self.tech,
            statut=Installation.Statut.EN_COURS)

        resp = _api(self.other).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('chantier_assigne', kinds)

    def test_scoping_cross_societe(self):
        """Un chantier d'une AUTRE société n'apparaît jamais, même pour un
        utilisateur homonyme (défense en profondeur du scoping serveur)."""
        from apps.installations.models import Installation
        other_company = _company('VX214 Chantier Co 2')
        outsider_tech = _user(other_company, 'vx214_tech_outsider')
        Installation.objects.create(
            company=other_company, reference='CH-VX214-X',
            client=_client(other_company), technicien_responsable=outsider_tech,
            statut=Installation.Statut.EN_COURS)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('chantier_assigne', kinds)


class Vx214InterventionDuJourTests(TestCase):

    def setUp(self):
        self.company = _company('VX214 Interv Co')
        self.tech = _user(self.company, 'vx214_interv_tech')

    def _installation(self):
        from apps.installations.models import Installation
        return Installation.objects.create(
            company=self.company, reference='CH-VX214-INT',
            client=_client(self.company))

    def test_intervention_du_jour_visible(self):
        from apps.installations.models import Intervention
        inst = self._installation()
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            technicien=self.tech, date_prevue=datetime.date.today())

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertIn('intervention_du_jour', kinds)

    def test_intervention_future_pas_encore_dans_ma_file(self):
        from apps.installations.models import Intervention
        inst = self._installation()
        futur = datetime.date.today() + datetime.timedelta(days=10)
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            technicien=self.tech, date_prevue=futur)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('intervention_du_jour', kinds)

    def test_intervention_validee_n_apparait_plus(self):
        from apps.installations.models import Intervention
        inst = self._installation()
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention=Intervention.Type.POSE,
            technicien=self.tech, date_prevue=datetime.date.today(),
            statut=Intervention.Statut.VALIDEE)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('intervention_du_jour', kinds)


class Vx214DemandeAchatACommanderTests(TestCase):

    def setUp(self):
        self.company = _company('VX214 DA Co')
        self.requester = _user(self.company, 'vx214_da_requester')

    def test_da_approuvee_visible_pour_le_demandeur(self):
        from apps.installations.models import DemandeAchat
        DemandeAchat.objects.create(
            company=self.company, reference='DA-VX214-1', objet='Câbles',
            created_by=self.requester, statut=DemandeAchat.Statut.APPROUVEE)

        resp = _api(self.requester).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertIn('da_approuvee_a_commander', kinds)

    def test_da_soumise_pas_encore_a_commander(self):
        from apps.installations.models import DemandeAchat
        DemandeAchat.objects.create(
            company=self.company, reference='DA-VX214-2', objet='Câbles',
            created_by=self.requester, statut=DemandeAchat.Statut.SOUMISE)

        resp = _api(self.requester).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('da_approuvee_a_commander', kinds)


class Vx214TicketTransfereTests(TestCase):

    def setUp(self):
        self.company = _company('VX214 Ticket Co')
        self.tech = _user(self.company, 'vx214_ticket_tech')

    def test_ticket_ouvert_assigne_visible(self):
        from apps.sav.models import Ticket
        Ticket.objects.create(
            company=self.company, reference='SAV-VX214-1',
            client=_client(self.company), technicien_responsable=self.tech,
            statut=Ticket.Statut.NOUVEAU)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertIn('ticket_transfere', kinds)

    def test_ticket_resolu_n_apparait_plus(self):
        from apps.sav.models import Ticket
        Ticket.objects.create(
            company=self.company, reference='SAV-VX214-2',
            client=_client(self.company), technicien_responsable=self.tech,
            statut=Ticket.Statut.RESOLU)

        resp = _api(self.tech).get('/api/django/records/activities/ma-file/')
        kinds = [it['kind'] for it in resp.data['items']]
        self.assertNotIn('ticket_transfere', kinds)


class Vx214NoParallelEndpointTests(TestCase):
    """Reshape imposé (grand-verdict) : PAS de `mes-affectations-entrantes/`
    ni de `MesAffectationsPage` — tout passe par `ma-file/` (VX83)."""

    def test_no_parallel_affectations_endpoint(self):
        company = _company('VX214 NoParallel Co')
        user = _user(company, 'vx214_noparallel')
        resp = _api(user).get('/api/django/installations/mes-affectations-entrantes/')
        self.assertEqual(resp.status_code, 404)
