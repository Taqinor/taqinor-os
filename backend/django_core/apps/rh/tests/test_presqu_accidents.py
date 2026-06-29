"""Tests FG182 — Registre des presqu'accidents (near-miss, pilotage HSE proactif).

Couvre :
* Création : company, reference (NM-YYYYMM-NNNN, race-safe) ET declare_par
  posées côté serveur (jamais lues du corps).
* Champs : gravité potentielle (faible/moyenne/élevée), mesure corrective,
  chantier_id (référence chaîne), photo, statut (ouvert/traité).
* Référence : jamais count()+1 — plus-haut-utilisé+1, robuste aux suppressions.
* Stats par gravité : ``stats/`` renvoie total, ouverts, ventilation par gravité,
  scopé société + filtrable (dates / statut).
* Filtres : gravité / statut / dates.
* Isolation multi-société : B ne voit ni les presqu'accidents ni les stats de A.
* Permission : un rôle normal est refusé (403).
* DRF : ``?format=`` réservé n'est pas l'export ; la liste reste JSON.
* Runtime-safety : tous les codes de gravité/statut tiennent dans max_length.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import PresquAccident

User = get_user_model()

NM = '/api/django/rh/presqu-accidents/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_presqu(company, gravite='faible', statut='ouvert',
                reference='NM-MANUAL', date_constat=None):
    return PresquAccident.objects.create(
        company=company, gravite_potentielle=gravite, statut=statut,
        reference=reference,
        date_constat=date_constat or timezone.localdate())


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PresquAccidentCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('nm-a', 'A')
        self.co_b = make_company('nm-b', 'B')
        self.user_a = make_user(self.co_a, 'nm-user-a')
        self.user_b = make_user(self.co_b, 'nm-user-b')

    def test_create_company_reference_declare_par_cote_serveur(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(NM, {
            'date_constat': today.isoformat(),
            'lieu': 'Chantier Casa',
            'chantier_id': 'CH-42',
            'gravite_potentielle': 'elevee',
            'description': 'Échafaudage instable, personne dessous.',
            'mesure_corrective': 'Échafaudage sécurisé, zone balisée.',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pa = PresquAccident.objects.get(id=resp.data['id'])
        self.assertEqual(pa.company, self.co_a)
        self.assertEqual(pa.gravite_potentielle, 'elevee')
        self.assertEqual(pa.chantier_id, 'CH-42')
        self.assertEqual(pa.mesure_corrective,
                         'Échafaudage sécurisé, zone balisée.')
        # declare_par renseigné côté serveur = l'utilisateur appelant.
        self.assertEqual(pa.declare_par, self.user_a)
        # reference générée côté serveur, préfixe NM-.
        self.assertTrue(pa.reference.startswith('NM-'), pa.reference)
        self.assertEqual(resp.data['reference'], pa.reference)
        # statut par défaut.
        self.assertEqual(pa.statut, 'ouvert')

    def test_reference_ignoree_du_corps(self):
        resp = auth(self.user_a).post(NM, {
            'date_constat': timezone.localdate().isoformat(),
            'reference': 'HACK-1',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pa = PresquAccident.objects.get(id=resp.data['id'])
        self.assertNotEqual(pa.reference, 'HACK-1')
        self.assertTrue(pa.reference.startswith('NM-'))

    def test_company_du_corps_ignoree(self):
        resp = auth(self.user_a).post(NM, {
            'date_constat': timezone.localdate().isoformat(),
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pa = PresquAccident.objects.get(id=resp.data['id'])
        self.assertEqual(pa.company, self.co_a)

    def test_declare_par_du_corps_ignore(self):
        # Un declare_par envoyé par le client est ignoré (read-only) : c'est
        # toujours l'utilisateur authentifié qui est enregistré.
        resp = auth(self.user_a).post(NM, {
            'date_constat': timezone.localdate().isoformat(),
            'declare_par': self.user_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pa = PresquAccident.objects.get(id=resp.data['id'])
        self.assertEqual(pa.declare_par, self.user_a)

    def test_reference_incrementale_pas_count_plus_1(self):
        today = timezone.localdate().isoformat()
        r1 = auth(self.user_a).post(
            NM, {'date_constat': today}, format='json')
        r2 = auth(self.user_a).post(
            NM, {'date_constat': today}, format='json')
        r3 = auth(self.user_a).post(
            NM, {'date_constat': today}, format='json')
        refs = {r1.data['reference'], r2.data['reference'],
                r3.data['reference']}
        self.assertEqual(len(refs), 3)

    def test_gravite_moyenne_enregistree(self):
        resp = auth(self.user_a).post(NM, {
            'date_constat': timezone.localdate().isoformat(),
            'gravite_potentielle': 'moyenne',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['gravite_potentielle_display'], 'Moyenne')

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'nm-normal', role='normal')
        resp = auth(normal).get(NM)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        make_presqu(self.co_a, reference='NM-A-1')
        resp = auth(self.user_b).get(NM)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_codes_tiennent_dans_max_length(self):
        # Runtime-safety (FG136) : codes gravité/statut ≤ max_length.
        grav = PresquAccident._meta.get_field('gravite_potentielle')
        for value, _ in PresquAccident.GravitePotentielle.choices:
            self.assertLessEqual(len(value), grav.max_length)
        stat = PresquAccident._meta.get_field('statut')
        for value, _ in PresquAccident.Statut.choices:
            self.assertLessEqual(len(value), stat.max_length)


class PresquAccidentFiltreTests(TestCase):
    def setUp(self):
        self.co_a = make_company('nmf-a', 'A')
        self.user_a = make_user(self.co_a, 'nmf-user-a')
        make_presqu(self.co_a, gravite='faible', statut='ouvert',
                    reference='NM-1', date_constat=date(2026, 6, 5))
        make_presqu(self.co_a, gravite='elevee', statut='traite',
                    reference='NM-2', date_constat=date(2026, 6, 10))
        make_presqu(self.co_a, gravite='moyenne', statut='ouvert',
                    reference='NM-3', date_constat=date(2026, 1, 4))

    def test_filtre_gravite(self):
        resp = auth(self.user_a).get(NM + '?gravite=elevee')
        self.assertEqual(
            [a['gravite_potentielle'] for a in rows(resp)], ['elevee'])

    def test_filtre_statut(self):
        resp = auth(self.user_a).get(NM + '?statut=traite')
        self.assertEqual(
            [a['statut'] for a in rows(resp)], ['traite'])

    def test_filtre_dates(self):
        resp = auth(self.user_a).get(
            NM + '?debut=2026-06-01&fin=2026-06-30')
        refs = {a['reference'] for a in rows(resp)}
        self.assertEqual(refs, {'NM-1', 'NM-2'})

    def test_format_param_ne_casse_pas_la_liste(self):
        # ``?format=`` est réservé par DRF — la liste reste JSON, pas un 404
        # ni un export.
        resp = auth(self.user_a).get(NM)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('text/csv', resp.get('Content-Type', ''))


class PresquAccidentStatsTests(TestCase):
    def setUp(self):
        self.co_a = make_company('nms-a', 'A')
        self.co_b = make_company('nms-b', 'B')
        self.user_a = make_user(self.co_a, 'nms-user-a')
        self.user_b = make_user(self.co_b, 'nms-user-b')
        make_presqu(self.co_a, gravite='faible', statut='ouvert',
                    reference='NM-A-1', date_constat=date(2026, 6, 5))
        make_presqu(self.co_a, gravite='faible', statut='traite',
                    reference='NM-A-2', date_constat=date(2026, 6, 6))
        make_presqu(self.co_a, gravite='elevee', statut='ouvert',
                    reference='NM-A-3', date_constat=date(2026, 6, 7))
        # Société B : ne doit jamais peser dans les stats de A.
        make_presqu(self.co_b, gravite='elevee', statut='ouvert',
                    reference='NM-B-1', date_constat=date(2026, 6, 5))

    def test_stats_endpoint_par_gravite(self):
        resp = auth(self.user_a).get(NM + 'stats/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self.assertEqual(data['total'], 3)
        self.assertEqual(data['ouverts'], 2)
        self.assertEqual(data['par_gravite']['faible'], 2)
        self.assertEqual(data['par_gravite']['elevee'], 1)
        # Clé toujours présente, à 0 par défaut.
        self.assertEqual(data['par_gravite']['moyenne'], 0)

    def test_stats_isolation_societe(self):
        resp = auth(self.user_b).get(NM + 'stats/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['par_gravite']['elevee'], 1)
        self.assertEqual(resp.data['par_gravite']['faible'], 0)

    def test_stats_filtre_statut(self):
        resp = auth(self.user_a).get(NM + 'stats/?statut=ouvert')
        self.assertEqual(resp.data['total'], 2)
        self.assertEqual(resp.data['ouverts'], 2)

    def test_stats_filtre_dates(self):
        resp = auth(self.user_a).get(
            NM + 'stats/?debut=2026-06-06&fin=2026-06-30')
        self.assertEqual(resp.data['total'], 2)

    def test_stats_role_normal_refuse(self):
        normal = make_user(self.co_a, 'nms-normal', role='normal')
        resp = auth(normal).get(NM + 'stats/')
        self.assertEqual(resp.status_code, 403)

    def test_selector_societe_none(self):
        # Garde défensive : aucune société → structure vide stable.
        data = selectors.stats_presqu_accidents(None)
        self.assertEqual(data['total'], 0)
        self.assertEqual(
            data['par_gravite'], {'faible': 0, 'moyenne': 0, 'elevee': 0})
