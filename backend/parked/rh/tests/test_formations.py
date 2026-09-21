"""Tests FG187 — Gestion de la formation (sessions / inscriptions / présence).

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ; intitulé,
  type interne/externe, organisme, dates, coût, statut, inscriptions imbriquées.
* FK même société : une ``competence_visee`` / un ``participant`` d'une autre
  société est refusé.
* Inscriptions imbriquées : participant / présence / résultat créés avec la
  company propagée côté serveur.
* Présence + résultat : champs portés par l'inscription.
* Marquer réalisée : l'action passe la session en ``realisee`` et, si une
  compétence est visée, met à jour (upsert) la matrice pour les PRÉSENTS
  seulement ; idempotente, scopée société (404 pour un autre tenant).
* CRUD : update remplace la liste d'inscriptions.
* Isolation multi-société : B ne voit ni ne crée les sessions de A.
* Permission : un rôle normal est refusé (403).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    Competence,
    CompetenceEmploye,
    DossierEmploye,
    InscriptionFormation,
    SessionFormation,
)

User = get_user_model()

URL = '/api/django/rh/sessions-formation/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Nom', prenom='Prenom'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def make_competence(company, code='POSE', libelle='Pose structure'):
    return Competence.objects.create(
        company=company, code=code, libelle=libelle)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class SessionCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('sf-a', 'A')
        self.co_b = make_company('sf-b', 'B')
        self.user_a = make_user(self.co_a, 'sf-user-a')
        self.user_b = make_user(self.co_b, 'sf-user-b')
        self.emp_a = make_employe(self.co_a, 'A-EMP', 'Bennani', 'Karim')
        self.comp_a = make_competence(self.co_a)

    def test_create_company_cote_serveur_avec_inscriptions(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(URL, {
            'intitule': 'Sécurité travail en hauteur',
            'type': 'externe',
            'organisme': 'OFPPT',
            'date_debut': today.isoformat(),
            'lieu': 'Casablanca',
            'cout': '4500.00',
            'competence_visee': self.comp_a.id,
            'notes': 'Session annuelle.',
            'inscriptions': [
                {'participant': self.emp_a.id, 'present': True,
                 'resultat': 'reussi', 'note': 'Bon niveau'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        session = SessionFormation.objects.get(id=resp.data['id'])
        self.assertEqual(session.company, self.co_a)
        self.assertEqual(session.type, 'externe')
        self.assertEqual(session.organisme, 'OFPPT')
        self.assertEqual(str(session.cout), '4500.00')
        self.assertEqual(session.competence_visee, self.comp_a)
        self.assertEqual(session.statut, 'planifiee')
        inscriptions = list(session.inscriptions.all())
        self.assertEqual(len(inscriptions), 1)
        self.assertEqual(inscriptions[0].company, self.co_a)
        self.assertTrue(inscriptions[0].present)
        self.assertEqual(inscriptions[0].resultat, 'reussi')
        self.assertEqual(len(resp.data['inscriptions']), 1)

    def test_company_du_corps_ignoree(self):
        resp = auth(self.user_a).post(URL, {
            'intitule': 'Formation',
            'date_debut': timezone.localdate().isoformat(),
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        session = SessionFormation.objects.get(id=resp.data['id'])
        self.assertEqual(session.company, self.co_a)

    def test_competence_autre_societe_refuse(self):
        comp_b = make_competence(self.co_b, code='B-POSE')
        resp = auth(self.user_a).post(URL, {
            'intitule': 'Formation',
            'date_debut': timezone.localdate().isoformat(),
            'competence_visee': comp_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('competence_visee', resp.data)

    def test_participant_autre_societe_refuse(self):
        emp_b = make_employe(self.co_b, 'B-EMP')
        resp = auth(self.user_a).post(URL, {
            'intitule': 'Formation',
            'date_debut': timezone.localdate().isoformat(),
            'inscriptions': [{'participant': emp_b.id}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'sf-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        SessionFormation.objects.create(
            company=self.co_a, intitule='X', date_debut=date(2026, 6, 1))
        resp = auth(self.user_b).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)


class SessionRealiseeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('sfr-a', 'A')
        self.co_b = make_company('sfr-b', 'B')
        self.user_a = make_user(self.co_a, 'sfr-user-a')
        self.user_b = make_user(self.co_b, 'sfr-user-b')
        self.comp_a = make_competence(self.co_a)
        self.present = make_employe(self.co_a, 'PRES', 'Present', 'P')
        self.absent = make_employe(self.co_a, 'ABS', 'Absent', 'A')
        self.session = SessionFormation.objects.create(
            company=self.co_a, intitule='Pose structure',
            date_debut=timezone.localdate(), competence_visee=self.comp_a)
        InscriptionFormation.objects.create(
            company=self.co_a, session=self.session,
            participant=self.present, present=True)
        InscriptionFormation.objects.create(
            company=self.co_a, session=self.session,
            participant=self.absent, present=False)

    def test_marquer_realisee_upsert_competence_presents_only(self):
        resp = auth(self.user_a).post(
            f'{URL}{self.session.id}/marquer-realisee/?niveau=4',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.session.refresh_from_db()
        self.assertEqual(self.session.statut, 'realisee')
        # Le présent a une ligne matrice au niveau demandé.
        ce = CompetenceEmploye.objects.get(
            employe=self.present, competence=self.comp_a)
        self.assertEqual(ce.company, self.co_a)
        self.assertEqual(ce.niveau, 4)
        self.assertEqual(ce.evalue_par, self.user_a)
        self.assertIsNotNone(ce.evalue_le)
        # L'absent n'a PAS de ligne matrice.
        self.assertFalse(
            CompetenceEmploye.objects.filter(
                employe=self.absent, competence=self.comp_a).exists())

    def test_marquer_realisee_met_a_jour_ligne_existante(self):
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.present,
            competence=self.comp_a, niveau=1)
        resp = auth(self.user_a).post(
            f'{URL}{self.session.id}/marquer-realisee/?niveau=3',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            CompetenceEmploye.objects.filter(
                employe=self.present, competence=self.comp_a).count(), 1)
        ce = CompetenceEmploye.objects.get(
            employe=self.present, competence=self.comp_a)
        self.assertEqual(ce.niveau, 3)

    def test_marquer_realisee_sans_competence_visee_pas_de_matrice(self):
        session = SessionFormation.objects.create(
            company=self.co_a, intitule='Libre',
            date_debut=timezone.localdate())
        InscriptionFormation.objects.create(
            company=self.co_a, session=session,
            participant=self.present, present=True)
        before = CompetenceEmploye.objects.count()
        resp = auth(self.user_a).post(
            f'{URL}{session.id}/marquer-realisee/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        session.refresh_from_db()
        self.assertEqual(session.statut, 'realisee')
        self.assertEqual(CompetenceEmploye.objects.count(), before)

    def test_marquer_realisee_idempotent(self):
        first = auth(self.user_a).post(
            f'{URL}{self.session.id}/marquer-realisee/', {}, format='json')
        self.assertEqual(first.status_code, 200)
        again = auth(self.user_a).post(
            f'{URL}{self.session.id}/marquer-realisee/', {}, format='json')
        self.assertEqual(again.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.statut, 'realisee')

    def test_marquer_realisee_autre_societe_404(self):
        resp = auth(self.user_b).post(
            f'{URL}{self.session.id}/marquer-realisee/', {}, format='json')
        self.assertEqual(resp.status_code, 404)


class SessionCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company('sfc-a', 'A')
        self.user_a = make_user(self.co_a, 'sfc-user-a')
        self.emp1 = make_employe(self.co_a, 'E1')
        self.emp2 = make_employe(self.co_a, 'E2')

    def test_update_remplace_inscriptions(self):
        session = SessionFormation.objects.create(
            company=self.co_a, intitule='X', date_debut=timezone.localdate())
        InscriptionFormation.objects.create(
            company=self.co_a, session=session, participant=self.emp1)
        resp = auth(self.user_a).patch(
            f'{URL}{session.id}/',
            {'lieu': 'Rabat',
             'inscriptions': [
                 {'participant': self.emp2.id, 'present': True},
             ]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        session.refresh_from_db()
        self.assertEqual(session.lieu, 'Rabat')
        parts = set(session.inscriptions.values_list(
            'participant_id', flat=True))
        self.assertEqual(parts, {self.emp2.id})

    def test_retrieve_et_delete(self):
        session = SessionFormation.objects.create(
            company=self.co_a, intitule='X', date_debut=timezone.localdate())
        get = auth(self.user_a).get(f'{URL}{session.id}/')
        self.assertEqual(get.status_code, 200)
        delete = auth(self.user_a).delete(f'{URL}{session.id}/')
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(
            SessionFormation.objects.filter(id=session.id).exists())

    def test_filtre_type_et_statut(self):
        SessionFormation.objects.create(
            company=self.co_a, intitule='Int', type='interne',
            date_debut=timezone.localdate(), statut='planifiee')
        SessionFormation.objects.create(
            company=self.co_a, intitule='Ext', type='externe',
            date_debut=timezone.localdate(), statut='realisee')
        resp = auth(self.user_a).get(f'{URL}?type=externe')
        self.assertEqual(resp.status_code, 200)
        intitules = {r['intitule'] for r in rows(resp)}
        self.assertEqual(intitules, {'Ext'})
