"""Tests FG183 — Causeries sécurité / toolbox talks (le quart d'heure sécurité).

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR (jamais lue du corps) ; thème,
  date, chantier (référence chaîne), animateur, participants imbriqués.
* FK même société : un ``animateur`` / ``participant`` d'une autre société est
  refusé (validation).
* Émargement : l'action ``emarger`` marque un participant comme ayant signé
  (présence + horodatage posé côté serveur), idempotente, 400 si le participant
  ne figure pas sur la feuille.
* CRUD : update remplace la liste de participants.
* Isolation multi-société : B ne voit ni ne crée les causeries de A.
* Permission : un rôle normal est refusé (403).
* DRF : ``?format=`` réservé ne casse pas la liste (reste JSON).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    CauserieParticipant,
    CauserieSecurite,
    DossierEmploye,
)

User = get_user_model()

URL = '/api/django/rh/causeries-securite/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Nom', prenom='Prenom'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CauserieCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cs-a', 'A')
        self.co_b = make_company('cs-b', 'B')
        self.user_a = make_user(self.co_a, 'cs-user-a')
        self.user_b = make_user(self.co_b, 'cs-user-b')
        self.anim_a = make_employe(self.co_a, 'A-ANIM', 'Bennani', 'Karim')
        self.p1_a = make_employe(self.co_a, 'A-P1', 'Alaoui', 'Sara')
        self.p2_a = make_employe(self.co_a, 'A-P2', 'Tazi', 'Omar')
        self.emp_b = make_employe(self.co_b, 'B-1', 'Idrissi', 'Yasmine')

    def test_create_company_cote_serveur_avec_participants(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(URL, {
            'theme': 'Port du harnais en hauteur',
            'date_causerie': today.isoformat(),
            'chantier_id': 'CH-42',
            'lieu': 'Toiture bât. B',
            'animateur': self.anim_a.id,
            'notes': 'Rappel des points d’ancrage.',
            'participants': [
                {'participant': self.p1_a.id},
                {'participant': self.p2_a.id, 'present': True},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        caus = CauserieSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(caus.company, self.co_a)
        self.assertEqual(caus.theme, 'Port du harnais en hauteur')
        self.assertEqual(caus.chantier_id, 'CH-42')
        self.assertEqual(caus.animateur, self.anim_a)
        # Participants créés, company propagée côté serveur.
        parts = list(caus.participants.all())
        self.assertEqual(len(parts), 2)
        for p in parts:
            self.assertEqual(p.company, self.co_a)
            self.assertFalse(p.emarge)
        self.assertEqual(len(resp.data['participants']), 2)

    def test_company_du_corps_ignoree(self):
        resp = auth(self.user_a).post(URL, {
            'theme': 'Consignation électrique',
            'date_causerie': timezone.localdate().isoformat(),
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        caus = CauserieSecurite.objects.get(id=resp.data['id'])
        self.assertEqual(caus.company, self.co_a)

    def test_animateur_autre_societe_refuse(self):
        emp_b = make_employe(self.co_b, 'B-ANIM')
        resp = auth(self.user_a).post(URL, {
            'theme': 'Gestes et postures',
            'date_causerie': timezone.localdate().isoformat(),
            'animateur': emp_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('animateur', resp.data)

    def test_participant_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'theme': 'EPI obligatoires',
            'date_causerie': timezone.localdate().isoformat(),
            'participants': [{'participant': self.emp_b.id}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('participants', resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'cs-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        CauserieSecurite.objects.create(
            company=self.co_a, theme='A', date_causerie=date(2026, 6, 1))
        resp = auth(self.user_b).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_format_param_ne_casse_pas_la_liste(self):
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('text/csv', resp.get('Content-Type', ''))


class CauserieEmargementTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cse-a', 'A')
        self.co_b = make_company('cse-b', 'B')
        self.user_a = make_user(self.co_a, 'cse-user-a')
        self.user_b = make_user(self.co_b, 'cse-user-b')
        self.p1 = make_employe(self.co_a, 'P1', 'Alaoui', 'Sara')
        self.p2 = make_employe(self.co_a, 'P2', 'Tazi', 'Omar')
        self.caus = CauserieSecurite.objects.create(
            company=self.co_a, theme='Harnais',
            date_causerie=timezone.localdate())
        self.lp1 = CauserieParticipant.objects.create(
            company=self.co_a, causerie=self.caus, participant=self.p1)
        self.lp2 = CauserieParticipant.objects.create(
            company=self.co_a, causerie=self.caus, participant=self.p2)

    def test_emarger_marque_present_et_horodate(self):
        resp = auth(self.user_a).post(
            f'{URL}{self.caus.id}/emarger/',
            {'participant': self.p1.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lp1.refresh_from_db()
        self.assertTrue(self.lp1.emarge)
        self.assertTrue(self.lp1.present)
        self.assertIsNotNone(self.lp1.emarge_le)
        # L'autre participant n'est pas affecté.
        self.lp2.refresh_from_db()
        self.assertFalse(self.lp2.emarge)

    def test_emarger_idempotent(self):
        first = auth(self.user_a).post(
            f'{URL}{self.caus.id}/emarger/',
            {'participant': self.p1.id}, format='json')
        self.assertEqual(first.status_code, 200)
        self.lp1.refresh_from_db()
        ts = self.lp1.emarge_le
        again = auth(self.user_a).post(
            f'{URL}{self.caus.id}/emarger/',
            {'participant': self.p1.id}, format='json')
        self.assertEqual(again.status_code, 200)
        self.lp1.refresh_from_db()
        # Horodatage conservé (pas réécrit), toujours une seule ligne.
        self.assertEqual(self.lp1.emarge_le, ts)
        self.assertEqual(
            self.caus.participants.filter(participant=self.p1).count(), 1)

    def test_emarger_participant_absent_400(self):
        etranger = make_employe(self.co_a, 'ETR')
        resp = auth(self.user_a).post(
            f'{URL}{self.caus.id}/emarger/',
            {'participant': etranger.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_emarger_sans_participant_400(self):
        resp = auth(self.user_a).post(
            f'{URL}{self.caus.id}/emarger/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_emarger_autre_societe_404(self):
        # Un utilisateur de B ne peut pas atteindre la causerie de A.
        resp = auth(self.user_b).post(
            f'{URL}{self.caus.id}/emarger/',
            {'participant': self.p1.id}, format='json')
        self.assertEqual(resp.status_code, 404)


class CauserieCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company('csc-a', 'A')
        self.user_a = make_user(self.co_a, 'csc-user-a')
        self.p1 = make_employe(self.co_a, 'P1')
        self.p2 = make_employe(self.co_a, 'P2')
        self.p3 = make_employe(self.co_a, 'P3')

    def test_update_remplace_participants(self):
        caus = CauserieSecurite.objects.create(
            company=self.co_a, theme='Init',
            date_causerie=timezone.localdate())
        CauserieParticipant.objects.create(
            company=self.co_a, causerie=caus, participant=self.p1)
        resp = auth(self.user_a).patch(
            f'{URL}{caus.id}/',
            {'theme': 'Mis à jour',
             'participants': [
                 {'participant': self.p2.id},
                 {'participant': self.p3.id},
             ]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        caus.refresh_from_db()
        self.assertEqual(caus.theme, 'Mis à jour')
        ids = set(caus.participants.values_list('participant_id', flat=True))
        self.assertEqual(ids, {self.p2.id, self.p3.id})

    def test_retrieve_et_delete(self):
        caus = CauserieSecurite.objects.create(
            company=self.co_a, theme='X',
            date_causerie=timezone.localdate())
        get = auth(self.user_a).get(f'{URL}{caus.id}/')
        self.assertEqual(get.status_code, 200)
        delete = auth(self.user_a).delete(f'{URL}{caus.id}/')
        self.assertEqual(delete.status_code, 204)
        self.assertFalse(
            CauserieSecurite.objects.filter(id=caus.id).exists())
