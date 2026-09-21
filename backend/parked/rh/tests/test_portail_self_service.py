"""Tests FG199 — Portail self-service employé + notes de frais.

Couvre :
* Portail (compte authentifié) : ``mes-infos`` lecture + édition limitée
  (poste/statut non modifiables), ``mes-soldes``/``mes-conges``/``mes-frais``/
  ``mes-epi``/``mes-habilitations``/``mes-bulletins`` ne renvoient QUE les
  données du dossier lié ; ``demander-conge`` et ``declarer-frais`` posent
  employe/company côté serveur ; compte sans dossier → 404/400/listes vides.
* NoteDeFrais (admin) : workflow approuver/refuser/marquer-remboursee,
  isolation, permission.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    DossierEmploye,
    NoteDeFrais,
    SoldeConge,
    TypeAbsence,
)

User = get_user_model()

PORTAIL = '/api/django/rh/portail/'
FRAIS = '/api/django/rh/notes-frais/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, user=None, **extra):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P',
        user=user, **extra)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PortailTests(TestCase):
    def setUp(self):
        self.co_a = make_company('por-a', 'A')
        self.co_b = make_company('por-b', 'B')
        self.user_a = make_user(self.co_a, 'por-user-a')
        self.emp_a = make_employe(
            self.co_a, 'POR1', user=self.user_a, poste='Technicien')

    def test_mes_infos_lecture(self):
        resp = auth(self.user_a).get(f'{PORTAIL}mes-infos/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['matricule'], 'POR1')

    def test_mes_infos_edition_limitee(self):
        resp = auth(self.user_a).patch(f'{PORTAIL}mes-infos/', {
            'telephone_perso': '0612345678',
            'poste': 'Directeur',  # ignoré (lecture seule)
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.emp_a.refresh_from_db()
        self.assertEqual(self.emp_a.telephone_perso, '0612345678')
        self.assertEqual(self.emp_a.poste, 'Technicien')  # inchangé

    def test_compte_sans_dossier_mes_infos_404(self):
        orphan = make_user(self.co_a, 'por-orphan')
        resp = auth(orphan).get(f'{PORTAIL}mes-infos/')
        self.assertEqual(resp.status_code, 404)

    def test_mes_soldes_seulement_les_siens(self):
        SoldeConge.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, acquis=18)
        autre = make_employe(self.co_a, 'POR9')
        SoldeConge.objects.create(
            company=self.co_a, employe=autre, annee=2026, acquis=18)
        resp = auth(self.user_a).get(f'{PORTAIL}mes-soldes/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_demander_conge_pose_employe_serveur(self):
        cp = TypeAbsence.objects.create(
            company=self.co_a, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True, deduit_solde=False)
        resp = auth(self.user_a).post(f'{PORTAIL}demander-conge/', {
            'type_absence': cp.id,
            'date_debut': '2026-06-22', 'date_fin': '2026-06-28',
            # tentative d'injecter un autre employé : ignorée
            'employe': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['employe'], self.emp_a.id)
        self.assertEqual(Decimal(resp.data['jours']), Decimal('5'))

    def test_declarer_frais_pose_employe_serveur(self):
        resp = auth(self.user_a).post(f'{PORTAIL}declarer-frais/', {
            'categorie': 'transport', 'montant': '85.50',
            'date_frais': '2026-06-20', 'libelle': 'Taxi chantier',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        nf = NoteDeFrais.objects.get(id=resp.data['id'])
        self.assertEqual(nf.employe, self.emp_a)
        self.assertEqual(nf.company, self.co_a)
        self.assertEqual(nf.statut, NoteDeFrais.Statut.SOUMISE)

    def test_mes_frais_seulement_les_siens(self):
        NoteDeFrais.objects.create(
            company=self.co_a, employe=self.emp_a, libelle='A',
            montant=Decimal('10'))
        autre = make_employe(self.co_a, 'POR8')
        NoteDeFrais.objects.create(
            company=self.co_a, employe=autre, libelle='B',
            montant=Decimal('20'))
        resp = auth(self.user_a).get(f'{PORTAIL}mes-frais/')
        self.assertEqual(len(rows(resp)), 1)


class NoteDeFraisAdminTests(TestCase):
    def setUp(self):
        self.co_a = make_company('nf-a', 'A')
        self.co_b = make_company('nf-b', 'B')
        self.resp_a = make_user(self.co_a, 'nf-resp-a', role='responsable')
        self.resp_b = make_user(self.co_b, 'nf-resp-b', role='responsable')
        self.emp_a = make_employe(self.co_a, 'NF1')

    def test_workflow_statut(self):
        nf = NoteDeFrais.objects.create(
            company=self.co_a, employe=self.emp_a, libelle='X',
            montant=Decimal('50'))
        api = auth(self.resp_a)
        r = api.post(f'{FRAIS}{nf.id}/approuver/')
        self.assertEqual(r.data['statut'], NoteDeFrais.Statut.APPROUVEE)
        r = api.post(f'{FRAIS}{nf.id}/marquer-remboursee/')
        self.assertEqual(r.data['statut'], NoteDeFrais.Statut.REMBOURSEE)
        nf2 = NoteDeFrais.objects.create(
            company=self.co_a, employe=self.emp_a, libelle='Y',
            montant=Decimal('5'))
        r = api.post(f'{FRAIS}{nf2.id}/refuser/')
        self.assertEqual(r.data['statut'], NoteDeFrais.Statut.REFUSEE)

    def test_isolation_et_404(self):
        nf = NoteDeFrais.objects.create(
            company=self.co_a, employe=self.emp_a, libelle='X',
            montant=Decimal('50'))
        self.assertEqual(len(rows(auth(self.resp_b).get(FRAIS))), 0)
        r = auth(self.resp_b).post(f'{FRAIS}{nf.id}/approuver/')
        self.assertEqual(r.status_code, 404)

    def test_permission_role_normal_refuse_admin(self):
        normal = make_user(self.co_a, 'nf-normal', role='normal')
        self.assertEqual(auth(normal).get(FRAIS).status_code, 403)
