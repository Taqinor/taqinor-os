"""Tests FG181 — Registre HSE & accidents du travail (déclaration + export CNSS).

Couvre :
* Création : company ET reference (AT-YYYYMM-NNNN, race-safe) posées côté
  serveur (jamais lues du corps), employe validé.
* Champs HSE : gravité (léger/grave/mortel), arrêt de travail + jours, photo,
  suivi CNSS (declare_cnss + date), statut.
* Référence : jamais count()+1 — plus-haut-utilisé+1, robuste aux suppressions.
* Cohérence : des jours d'arrêt sans arrêt déclaré sont refusés (400).
* Export CNSS : ``?export=csv`` (et ``export-cnss/``) renvoie un CSV avec les
  champs d'une déclaration d'accident CNSS, scopé société + filtré.
* Filtres : gravité / statut / employé.
* Cross-société : employé d'une autre société refusé (400).
* Isolation multi-société : B ne voit pas les accidents de A.
* Permission : un rôle normal est refusé (403).
* Runtime-safety : tous les codes de gravité/statut tiennent dans max_length.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import AccidentTravail, DossierEmploye

User = get_user_model()

ACC = '/api/django/rh/accidents-travail/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, cin=''):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E', cin=cin)


def make_accident(company, employe, gravite='leger', statut='declare',
                  reference='AT-MANUAL', date_accident=None):
    return AccidentTravail.objects.create(
        company=company, employe=employe, gravite=gravite, statut=statut,
        reference=reference,
        date_accident=date_accident or timezone.localdate())


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class AccidentTravailCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('at-a', 'A')
        self.co_b = make_company('at-b', 'B')
        self.user_a = make_user(self.co_a, 'at-user-a')
        self.user_b = make_user(self.co_b, 'at-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_create_company_et_reference_posees_cote_serveur(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(ACC, {
            'employe': self.emp_a.id,
            'date_accident': today.isoformat(),
            'lieu': 'Chantier Casa',
            'gravite': 'grave',
            'description': 'Chute depuis la structure.',
            'arret_travail': True,
            'nb_jours_arret': 12,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        acc = AccidentTravail.objects.get(id=resp.data['id'])
        self.assertEqual(acc.company, self.co_a)
        self.assertEqual(acc.gravite, 'grave')
        self.assertTrue(acc.arret_travail)
        self.assertEqual(acc.nb_jours_arret, 12)
        # Référence générée côté serveur, préfixe AT-.
        self.assertTrue(acc.reference.startswith('AT-'), acc.reference)
        self.assertEqual(resp.data['reference'], acc.reference)
        self.assertEqual(acc.statut, 'declare')

    def test_reference_ignoree_du_corps(self):
        # Une référence envoyée par le client est ignorée (read-only).
        resp = auth(self.user_a).post(ACC, {
            'employe': self.emp_a.id,
            'date_accident': timezone.localdate().isoformat(),
            'reference': 'HACK-1',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        acc = AccidentTravail.objects.get(id=resp.data['id'])
        self.assertNotEqual(acc.reference, 'HACK-1')
        self.assertTrue(acc.reference.startswith('AT-'))

    def test_company_du_corps_ignoree(self):
        resp = auth(self.user_a).post(ACC, {
            'employe': self.emp_a.id,
            'date_accident': timezone.localdate().isoformat(),
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        acc = AccidentTravail.objects.get(id=resp.data['id'])
        self.assertEqual(acc.company, self.co_a)

    def test_reference_incrementale_pas_count_plus_1(self):
        # Deux créations → numéros distincts ; une suppression ne fait jamais
        # retomber sur un numéro déjà utilisé (anti-count()+1).
        today = timezone.localdate().isoformat()
        r1 = auth(self.user_a).post(
            ACC, {'employe': self.emp_a.id, 'date_accident': today},
            format='json')
        r2 = auth(self.user_a).post(
            ACC, {'employe': self.emp_a.id, 'date_accident': today},
            format='json')
        ref1 = r1.data['reference']
        ref2 = r2.data['reference']
        self.assertNotEqual(ref1, ref2)
        # On supprime le 2e et on recrée : on ne doit pas réobtenir ref2.
        AccidentTravail.objects.get(id=r2.data['id']).delete()
        r3 = auth(self.user_a).post(
            ACC, {'employe': self.emp_a.id, 'date_accident': today},
            format='json')
        self.assertNotEqual(r3.data['reference'], ref1)
        self.assertNotEqual(r3.data['reference'], ref2)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(ACC, {
            'employe': self.emp_b.id,
            'date_accident': timezone.localdate().isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_jours_arret_sans_arret_refuse(self):
        resp = auth(self.user_a).post(ACC, {
            'employe': self.emp_a.id,
            'date_accident': timezone.localdate().isoformat(),
            'arret_travail': False,
            'nb_jours_arret': 5,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_gravite_mortel_enregistree(self):
        resp = auth(self.user_a).post(ACC, {
            'employe': self.emp_a.id,
            'date_accident': timezone.localdate().isoformat(),
            'gravite': 'mortel',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['gravite_display'], 'Mortel')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'at-normal', role='normal')
        resp = auth(normal).get(ACC)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        make_accident(self.co_a, self.emp_a, reference='AT-A-1')
        resp = auth(self.user_b).get(ACC)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_codes_tiennent_dans_max_length(self):
        # Runtime-safety (FG136) : codes gravité/statut ≤ max_length.
        grav = AccidentTravail._meta.get_field('gravite')
        for value, _ in AccidentTravail.Gravite.choices:
            self.assertLessEqual(len(value), grav.max_length)
        stat = AccidentTravail._meta.get_field('statut')
        for value, _ in AccidentTravail.Statut.choices:
            self.assertLessEqual(len(value), stat.max_length)


class AccidentTravailFiltreTests(TestCase):
    def setUp(self):
        self.co_a = make_company('atf-a', 'A')
        self.user_a = make_user(self.co_a, 'atf-user-a')
        self.emp1 = make_employe(self.co_a, 'E1')
        self.emp2 = make_employe(self.co_a, 'E2')
        make_accident(self.co_a, self.emp1, gravite='leger',
                      statut='declare', reference='AT-1')
        make_accident(self.co_a, self.emp1, gravite='grave',
                      statut='clos', reference='AT-2')
        make_accident(self.co_a, self.emp2, gravite='mortel',
                      statut='declare', reference='AT-3')

    def test_filtre_gravite(self):
        resp = auth(self.user_a).get(ACC + '?gravite=grave')
        self.assertEqual(
            [a['gravite'] for a in rows(resp)], ['grave'])

    def test_filtre_statut(self):
        resp = auth(self.user_a).get(ACC + '?statut=clos')
        self.assertEqual(
            [a['statut'] for a in rows(resp)], ['clos'])

    def test_filtre_employe(self):
        resp = auth(self.user_a).get(ACC + f'?employe={self.emp2.id}')
        refs = {a['reference'] for a in rows(resp)}
        self.assertEqual(refs, {'AT-3'})


class AccidentTravailExportCnssTests(TestCase):
    def setUp(self):
        self.co_a = make_company('atx-a', 'A')
        self.co_b = make_company('atx-b', 'B')
        self.user_a = make_user(self.co_a, 'atx-user-a')
        self.user_b = make_user(self.co_b, 'atx-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1', cin='AB12345')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.acc = AccidentTravail.objects.create(
            company=self.co_a, employe=self.emp_a, reference='AT-202606-0001',
            date_accident=date(2026, 6, 10), lieu='Chantier Rabat',
            gravite='grave', description='Chute',
            arret_travail=True, nb_jours_arret=7,
            declare_cnss=True, date_declaration_cnss=date(2026, 6, 12),
            statut='declare')
        # Accident d'une autre société : ne doit jamais apparaître.
        AccidentTravail.objects.create(
            company=self.co_b, employe=self.emp_b, reference='AT-B-1',
            date_accident=date(2026, 6, 10), gravite='leger')

    def test_export_csv_query_param(self):
        resp = auth(self.user_a).get(ACC + '?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8-sig')
        self.assertIn('Reference', body)
        self.assertIn('AT-202606-0001', body)
        self.assertIn('AB12345', body)
        self.assertIn('Chantier Rabat', body)
        # Champs CNSS clés présents.
        self.assertIn('Declare CNSS', body)
        self.assertIn('2026-06-12', body)
        # Isolation société : pas l'accident de B.
        self.assertNotIn('AT-B-1', body)

    def test_export_cnss_action(self):
        resp = auth(self.user_a).get(ACC + 'export-cnss/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('AT-202606-0001', resp.content.decode('utf-8-sig'))

    def test_export_filtre_gravite(self):
        AccidentTravail.objects.create(
            company=self.co_a, employe=self.emp_a, reference='AT-202606-0002',
            date_accident=date(2026, 6, 11), gravite='leger')
        resp = auth(self.user_a).get(ACC + '?export=csv&gravite=grave')
        body = resp.content.decode('utf-8-sig')
        self.assertIn('AT-202606-0001', body)
        self.assertNotIn('AT-202606-0002', body)

    def test_export_filtre_dates(self):
        AccidentTravail.objects.create(
            company=self.co_a, employe=self.emp_a, reference='AT-202601-0001',
            date_accident=date(2026, 1, 5), gravite='leger')
        resp = auth(self.user_a).get(
            ACC + '?export=csv&debut=2026-06-01&fin=2026-06-30')
        body = resp.content.decode('utf-8-sig')
        self.assertIn('AT-202606-0001', body)
        self.assertNotIn('AT-202601-0001', body)

    def test_export_isolation_societe(self):
        resp = auth(self.user_b).get(ACC + '?export=csv')
        body = resp.content.decode('utf-8-sig')
        self.assertIn('AT-B-1', body)
        self.assertNotIn('AT-202606-0001', body)

    def test_export_role_normal_refuse(self):
        normal = make_user(self.co_a, 'atx-normal', role='normal')
        resp = auth(normal).get(ACC + '?export=csv')
        self.assertEqual(resp.status_code, 403)

    def test_format_param_404_export_uses_export(self):
        # ``?format=csv`` est réservé par DRF (et ne déclenche pas l'export) ;
        # l'export passe par ``?export=csv``. On vérifie que la liste normale
        # (sans export) reste JSON paginée.
        resp = auth(self.user_a).get(ACC)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('text/csv', resp['Content-Type'])
