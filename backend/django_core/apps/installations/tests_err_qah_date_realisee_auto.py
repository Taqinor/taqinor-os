"""
ERR-QAH-CHANTIERS-INTERVENTION-DATE-REALISEE-AUTO (qa-explorer, 2026-09-28).

Une intervention créée depuis l'onglet « Interventions » du chantier recevait
`date_realisee` = aujourd'hui alors qu'elle est prévue plus tard et encore
« À préparer » : `_stamp_date_realisee` (apps/installations/views/
intervention.py) tamponnait la date dès qu'un `compte_rendu` était renseigné,
or le mini-formulaire du chantier n'offre QUE ce champ pour toute note.

Couvre :
  * le repro exact du constat qa-explorer (POST create, type pose, date_prevue
    demain, compte_rendu rempli, pas de date_realisee) → 201, date_realisee
    reste NULL, statut reste « À préparer » ;
  * le chemin légitime de terminaison (statut Terminée/Validée) continue bien
    de tamponner la date réalisée.

Run :
    python manage.py test apps.installations.tests_err_qah_date_realisee_auto -v2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Installation, Intervention
from apps.installations.views.intervention import InterventionViewSet

User = get_user_model()


def make_company(slug='err-qah-date-co', nom='ErrQah DateCo'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_accepted_devis(company):
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'errqah-date-{company.id}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    from decimal import Decimal
    devis = Devis.objects.create(
        company=company, reference=f'DEV-ERRQAH-DATE-{company.id}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    return devis


class TestInterventionDateRealiseeNotAutoStampedOnCompteRendu(TestCase):
    """Repro exact du constat qa-explorer : création depuis l'onglet
    « Interventions » du chantier avec un compte rendu, date prévue future."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='err_qah_date_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        devis = make_accepted_devis(self.company)
        created = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.inst = Installation.objects.get(pk=created.data['id'])

    def test_create_with_compte_rendu_and_future_date_prevue_leaves_date_realisee_null(self):
        demain = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'pose',
            'date_prevue': demain, 'compte_rendu': 'test',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['date_realisee'])
        self.assertEqual(r.data['statut'], Intervention.Statut.A_PREPARER)
        interv = Intervention.objects.get(pk=r.data['id'])
        self.assertIsNone(interv.date_realisee)
        self.assertEqual(interv.statut, Intervention.Statut.A_PREPARER)
        self.assertEqual(interv.compte_rendu, 'test')

    def test_edit_adding_compte_rendu_does_not_stamp_date_realisee(self):
        created = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'controle',
            'date_prevue': (timezone.localdate() + timedelta(days=2)).isoformat(),
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        iv_id = created.data['id']
        r = self.api.patch(
            f'/api/django/installations/interventions/{iv_id}/',
            {'compte_rendu': 'RAS'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        interv = Intervention.objects.get(pk=iv_id)
        self.assertIsNone(interv.date_realisee)
        self.assertEqual(interv.statut, Intervention.Statut.A_PREPARER)


class TestStampDateRealiseeUnit(TestCase):
    """Unit-teste directement la fonction corrigée : seul le statut de
    complétion (Terminée/Validée) tamponne — jamais un simple compte_rendu."""

    def setUp(self):
        self.company = make_company(slug='err-qah-date-co-unit', nom='ErrQah Unit')
        self.user = User.objects.create_user(
            username='err_qah_date_unit', password='x', role_legacy='responsable',
            company=self.company)

    def _interv(self, **kwargs):
        return Intervention.objects.create(
            company=self.company, type_intervention='controle',
            created_by=self.user, **kwargs)

    def test_compte_rendu_alone_never_stamps(self):
        interv = self._interv(
            compte_rendu='test', statut=Intervention.Statut.A_PREPARER)
        InterventionViewSet._stamp_date_realisee(interv)
        interv.refresh_from_db()
        self.assertIsNone(interv.date_realisee)

    def test_statut_terminee_stamps_today(self):
        interv = self._interv(statut=Intervention.Statut.TERMINEE)
        InterventionViewSet._stamp_date_realisee(interv)
        interv.refresh_from_db()
        self.assertEqual(interv.date_realisee, date.today())

    def test_statut_validee_stamps_today(self):
        interv = self._interv(statut=Intervention.Statut.VALIDEE)
        InterventionViewSet._stamp_date_realisee(interv)
        interv.refresh_from_db()
        self.assertEqual(interv.date_realisee, date.today())

    def test_never_overwrites_existing_date_realisee(self):
        existing = date(2026, 1, 1)
        interv = self._interv(
            statut=Intervention.Statut.TERMINEE, date_realisee=existing)
        InterventionViewSet._stamp_date_realisee(interv)
        interv.refresh_from_db()
        self.assertEqual(interv.date_realisee, existing)
