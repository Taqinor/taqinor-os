"""Tests AUDV11 — Endpoints REST manquants identifiés par le rapport-orphelines
(DRAFT165-85..90/97/79) : le cycle d'approbation de clôture NCR (ARC10), la
création de SCAR depuis une NCR, et les relances dérogations/étapes AT/MP
avaient tous un service testé (test_arc10_workflow_cloture_ncr.py,
test_xqhs6_scar.py) mais AUCUN endpoint pour les atteindre depuis un écran.

Couvre :

* ``POST …/non-conformites/<id>/demarrer-cloture/`` — démarre le cycle ARC10 ;
* ``POST …/non-conformites/<id>/approuver-cloture/`` — fait avancer/clôture ;
* ``POST …/non-conformites/<id>/rejeter-cloture/`` — stoppe le cycle ;
* ``POST …/non-conformites/<id>/escalader-cloture/`` — marque l'étape escaladée ;
* ``POST …/non-conformites/<id>/creer-scar/`` — SCAR fournisseur depuis la NCR ;
* ``POST …/derogations/relancer/`` et ``…/etapes-declaration-at/relancer/`` ;
* le compteur SCAR advisory sur ``stock`` ``supplier_performance``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import DemandeActionFournisseur, Derogation, NonConformite
from apps.qhse.services import demarrer_workflow_cloture_ncr
from apps.stock.models import Fournisseur
from apps.stock.services import supplier_performance
from core.models import WorkflowInstance

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_ncr(company, titre='NCR', **kwargs):
    return NonConformite.objects.create(company=company, titre=titre, **kwargs)


class CloturNcrWorkflowApiTests(TestCase):
    BASE = '/api/django/qhse/non-conformites/{}/{}/'

    def setUp(self):
        self.co = make_company('audv11-workflow', 'Workflow')
        self.user = make_user(self.co, 'audv11-workflow-user')
        self.ncr = make_ncr(self.co)

    def test_demarrer_cloture_cree_une_instance(self):
        resp = auth(self.user).post(self.BASE.format(self.ncr.id, 'demarrer-cloture'))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(
            WorkflowInstance.objects.filter(
                company=self.co, definition__code='cloture_ncr').count(), 1)

    def test_demarrer_cloture_ncr_deja_cloturee_400(self):
        self.ncr.statut = NonConformite.Statut.CLOTUREE
        self.ncr.save(update_fields=['statut'])
        resp = auth(self.user).post(self.BASE.format(self.ncr.id, 'demarrer-cloture'))
        self.assertEqual(resp.status_code, 400)

    def test_approuver_cloture_fait_avancer_puis_cloture(self):
        now = timezone.make_aware(datetime.datetime(2026, 6, 29, 8, 0, 0))
        demarrer_workflow_cloture_ncr(self.ncr, now=now)

        first = auth(self.user).post(
            self.BASE.format(self.ncr.id, 'approuver-cloture'),
            {'commentaire': 'Vérifié agent'}, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['statut'], WorkflowInstance.STATUT_EN_COURS)
        self.ncr.refresh_from_db()
        self.assertNotEqual(self.ncr.statut, NonConformite.Statut.CLOTUREE)

        second = auth(self.user).post(self.BASE.format(self.ncr.id, 'approuver-cloture'))
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['statut'], WorkflowInstance.STATUT_TERMINE)
        self.assertEqual(second.data['ncr']['statut'], NonConformite.Statut.CLOTUREE)

    def test_approuver_cloture_sans_cycle_400(self):
        resp = auth(self.user).post(self.BASE.format(self.ncr.id, 'approuver-cloture'))
        self.assertEqual(resp.status_code, 400)

    def test_rejeter_cloture_stoppe_le_cycle(self):
        demarrer_workflow_cloture_ncr(self.ncr)
        resp = auth(self.user).post(
            self.BASE.format(self.ncr.id, 'rejeter-cloture'),
            {'commentaire': 'Incomplet'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], WorkflowInstance.STATUT_TERMINE)
        self.assertNotEqual(resp.data['ncr']['statut'], NonConformite.Statut.CLOTUREE)

    def test_escalader_cloture_marque_letape(self):
        demarrer_workflow_cloture_ncr(self.ncr)
        resp = auth(self.user).post(self.BASE.format(self.ncr.id, 'escalader-cloture'))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ordre'], 1)

    def test_escalader_cloture_sans_cycle_400(self):
        resp = auth(self.user).post(self.BASE.format(self.ncr.id, 'escalader-cloture'))
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_refuse(self):
        normal = make_user(self.co, 'audv11-normal', role='normal')
        resp = auth(normal).post(self.BASE.format(self.ncr.id, 'demarrer-cloture'))
        self.assertEqual(resp.status_code, 403)

    def test_autre_societe_404(self):
        other = make_company('audv11-workflow-b', 'B')
        other_user = make_user(other, 'audv11-workflow-b-user')
        resp = auth(other_user).post(self.BASE.format(self.ncr.id, 'demarrer-cloture'))
        self.assertEqual(resp.status_code, 404)


class CreerScarDepuisNcrApiTests(TestCase):
    BASE = '/api/django/qhse/non-conformites/{}/creer-scar/'

    def setUp(self):
        self.co = make_company('audv11-scar', 'Scar')
        self.user = make_user(self.co, 'audv11-scar-user')
        self.fournisseur = Fournisseur.objects.create(company=self.co, nom='Fourn X')

    def test_cree_scar_depuis_ncr_fournisseur(self):
        ncr = make_ncr(self.co, fournisseur=self.fournisseur, titre='NCR réception')
        resp = auth(self.user).post(
            self.BASE.format(ncr.id),
            {'echeance_reponse': '2026-10-01'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        scar = DemandeActionFournisseur.objects.get(id=resp.data['id'])
        self.assertEqual(scar.ncr_source_id, ncr.id)
        self.assertEqual(scar.fournisseur_id, self.fournisseur.id)
        self.assertEqual(scar.statut, DemandeActionFournisseur.Statut.EMISE)

    def test_ncr_sans_fournisseur_400(self):
        ncr = make_ncr(self.co, titre='NCR sans fournisseur')
        resp = auth(self.user).post(self.BASE.format(ncr.id))
        self.assertEqual(resp.status_code, 400)


class RelancerDerogationsApiTests(TestCase):
    BASE = '/api/django/qhse/derogations/relancer/'

    def setUp(self):
        self.co = make_company('audv11-derog', 'Derog')
        self.user = make_user(self.co, 'audv11-derog-user')

    def test_relance_derogation_a_echeance(self):
        ncr = make_ncr(self.co)
        Derogation.objects.create(
            company=self.co, non_conformite=ncr,
            date_expiration=timezone.localdate(),
            approbateur=self.user,
        )
        resp = auth(self.user).post(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)


class RelancerEtapesAtApiTests(TestCase):
    BASE = '/api/django/qhse/etapes-declaration-at/relancer/'

    def setUp(self):
        self.co = make_company('audv11-etapeat', 'EtapeAt')
        self.user = make_user(self.co, 'audv11-etapeat-user')

    def test_relance_repond_200(self):
        # Aucune étape en retard créée : couvre au minimum le câblage REST
        # (le digest vide est un comportement valide, cf. relancer_derogations).
        resp = auth(self.user).post(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 0)


class ScarCounterSupplierPerformanceTests(TestCase):
    """DRAFT165-79 — le scorecard fournisseur affiche le compteur SCAR."""

    def setUp(self):
        self.co = make_company('audv11-scorecard', 'Scorecard')
        self.fournisseur = Fournisseur.objects.create(company=self.co, nom='Fourn Y')

    def test_scorecard_inclut_le_compteur_scar(self):
        ncr = make_ncr(self.co, fournisseur=self.fournisseur)
        DemandeActionFournisseur.objects.create(
            company=self.co, fournisseur=self.fournisseur, ncr_source=ncr,
        )
        result = supplier_performance(self.co, self.fournisseur)
        self.assertEqual(result['scar_total'], 1)
        self.assertEqual(result['scar_ouvertes'], 1)
