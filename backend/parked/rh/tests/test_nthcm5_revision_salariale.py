"""Tests NTHCM5 — cycles de révision salariale avec enveloppe par manager.

Couvre :
* créer un cycle + des enveloppes manager ;
* un manager propose DANS son enveloppe (201) ;
* il dépasse son enveloppe → 400 avec un message FR explicite ;
* il propose pour un NON-subordonné → 403 ;
* la permission ``salaires_voir`` gate lecture ET écriture (403 sinon) ;
* snapshot du salaire + montant calculés côté serveur ;
* isolation société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    CycleRevisionSalariale,
    DossierEmploye,
    EnveloppeManager,
    PropositionRevision,
    Remuneration,
)
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, permissions=('salaires_voir',)):
    role = Role.objects.create(
        company=company, nom=f'role-{username}', permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RevisionSalarialeTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm5-a', 'A')
        self.user_manager = make_user(self.co, 'nthcm5-manager')
        self.manager = DossierEmploye.objects.create(
            company=self.co, matricule='MGR-1', nom='Chef', prenom='Equipe',
            user=self.user_manager)
        self.sub1 = DossierEmploye.objects.create(
            company=self.co, matricule='SUB-1', nom='Alpha', prenom='Un',
            manager=self.manager)
        self.sub2 = DossierEmploye.objects.create(
            company=self.co, matricule='SUB-2', nom='Beta', prenom='Deux',
            manager=self.manager)
        self.hors_equipe = DossierEmploye.objects.create(
            company=self.co, matricule='OUT-1', nom='Gamma', prenom='Trois')
        Remuneration.objects.create(
            company=self.co, employe=self.sub1, montant=Decimal('10000'),
            date_effet='2026-01-01')
        self.cycle = CycleRevisionSalariale.objects.create(
            company=self.co, libelle='Révision 2027', periode='2027',
            statut=CycleRevisionSalariale.Statut.OUVERT)
        EnveloppeManager.objects.create(
            company=self.co, cycle=self.cycle, manager=self.manager,
            enveloppe_pct=Decimal('5'))
        self.api = auth(self.user_manager)

    def _proposer(self, employe, pct, justification=''):
        return self.api.post(
            '/api/django/rh/propositions-revision/',
            {'cycle': self.cycle.id, 'employe': employe.id,
             'augmentation_pct_proposee': str(pct),
             'justification': justification},
            format='json')

    def test_proposition_dans_l_enveloppe_ok(self):
        resp = self._proposer(self.sub1, '3')
        self.assertEqual(resp.status_code, 201, resp.data)
        proposition = PropositionRevision.objects.get(
            cycle=self.cycle, employe=self.sub1)
        # Snapshot + montant posés CÔTÉ SERVEUR.
        self.assertEqual(proposition.salaire_actuel, Decimal('10000.00'))
        self.assertEqual(
            proposition.augmentation_montant_proposee, Decimal('300.00'))
        self.assertEqual(proposition.propose_par_id, self.user_manager.id)
        self.assertEqual(proposition.company_id, self.co.id)

    def test_depassement_enveloppe_400_message_explicite(self):
        self.assertEqual(self._proposer(self.sub1, '3').status_code, 201)
        resp = self._proposer(self.sub2, '4')
        self.assertEqual(resp.status_code, 400, resp.data)
        message = str(resp.data)
        self.assertIn('Enveloppe dépassée', message)
        self.assertFalse(
            PropositionRevision.objects.filter(employe=self.sub2).exists())

    def test_proposition_pour_non_subordonne_403(self):
        resp = self._proposer(self.hors_equipe, '1')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(
            PropositionRevision.objects.filter(
                employe=self.hors_equipe).exists())

    def test_sans_enveloppe_toute_proposition_est_refusee(self):
        autre_user = make_user(self.co, 'nthcm5-mgr2')
        autre_manager = DossierEmploye.objects.create(
            company=self.co, matricule='MGR-2', nom='Autre', prenom='Chef',
            user=autre_user)
        subordonne = DossierEmploye.objects.create(
            company=self.co, matricule='SUB-9', nom='Delta', prenom='Neuf',
            manager=autre_manager)
        resp = auth(autre_user).post(
            '/api/django/rh/propositions-revision/',
            {'cycle': self.cycle.id, 'employe': subordonne.id,
             'augmentation_pct_proposee': '1'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_mise_a_jour_ne_double_compte_pas_l_enveloppe(self):
        self.assertEqual(self._proposer(self.sub1, '3').status_code, 201)
        # Re-proposer 5 % pour LE MÊME employé : les 3 % précédents sont
        # remplacés, pas cumulés — 5 % tient exactement dans l'enveloppe.
        resp = self._proposer(self.sub1, '5')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            PropositionRevision.objects.filter(cycle=self.cycle).count(), 1)

    def test_proposition_rejetee_rend_l_enveloppe(self):
        self._proposer(self.sub1, '5')
        proposition = PropositionRevision.objects.get(employe=self.sub1)
        proposition.statut = PropositionRevision.Statut.REJETEE
        proposition.save(update_fields=['statut'])
        self.assertEqual(
            services.enveloppe_consommee(self.cycle, self.manager),
            Decimal('0'))
        self.assertEqual(self._proposer(self.sub2, '5').status_code, 201)

    def test_isolation_societe(self):
        co_b = make_company('nthcm5-b', 'B')
        user_b = make_user(co_b, 'nthcm5-b-user')
        resp = auth(user_b).get('/api/django/rh/cycles-revision/')
        self.assertEqual(resp.status_code, 200, resp.data)
        resultats = (resp.data['results'] if isinstance(resp.data, dict)
                     else resp.data)
        self.assertEqual(len(resultats), 0)


class GateSalairesVoirTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm5-gate', 'G')
        self.avec_droit = make_user(self.co, 'nthcm5-avec-droit')

    def test_lecture_refusee_sans_salaires_voir(self):
        user = make_user(
            self.co, 'nthcm5-lecture', permissions=['rh_voir'])
        resp = auth(user).get('/api/django/rh/cycles-revision/')
        self.assertEqual(resp.status_code, 403)

    def test_lecture_autorisee_avec_salaires_voir(self):
        resp = auth(self.avec_droit).get('/api/django/rh/cycles-revision/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_creation_cycle_pose_la_societe_cote_serveur(self):
        resp = auth(self.avec_droit).post(
            '/api/django/rh/cycles-revision/',
            {'libelle': 'Révision 2028', 'periode': '2028'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cycle = CycleRevisionSalariale.objects.get(id=resp.data['id'])
        self.assertEqual(cycle.company_id, self.co.id)
        self.assertEqual(
            cycle.statut, CycleRevisionSalariale.Statut.BROUILLON)
