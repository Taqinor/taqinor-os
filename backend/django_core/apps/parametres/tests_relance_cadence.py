"""RELANCE FOUNDATION — gabarit de cadence de relance par défaut (founder-
editable), consommé par ``apps.crm.services.initialiser_plan_relance``.

Couvre : seed idempotent additif, seed à la volée pour une société sans
cadence, API (lecture ouverte, écriture réservée admin/responsable, company
forcée côté serveur, non-migration de l'``ordre`` d'un barreau existant).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models_relance import (
    CADENCE_RELANCE_DEFAUT, CadenceRelanceEtape,
)

User = get_user_model()

CADENCE_URL = '/api/django/parametres/cadence-relance/'


def _company(slug='cad-relance-co', nom='Cadence Relance Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CadenceRelanceEtapeModelTest(TestCase):
    def test_seed_defaults_cree_les_cinq_barreaux_neutres(self):
        company = _company('cad-relance-seed')
        created = CadenceRelanceEtape.seed_defaults(company)
        self.assertEqual(created, len(CADENCE_RELANCE_DEFAUT))
        delais = list(
            CadenceRelanceEtape.objects.filter(company=company)
            .order_by('ordre').values_list('delai_jours', flat=True))
        self.assertEqual(delais, [2, 5, 10, 20, 35])

    def test_seed_defaults_ne_retouche_jamais_un_barreau_personnalise(self):
        company = _company('cad-relance-idem')
        CadenceRelanceEtape.seed_defaults(company)
        etape = CadenceRelanceEtape.objects.get(company=company, ordre=1)
        etape.canal = 'visite'
        etape.save(update_fields=['canal'])
        self.assertEqual(CadenceRelanceEtape.seed_defaults(company), 0)
        etape.refresh_from_db()
        self.assertEqual(etape.canal, 'visite')

    def test_cadence_pour_seed_a_la_volee(self):
        company = _company('cad-relance-lazy')
        self.assertFalse(CadenceRelanceEtape.objects.filter(company=company).exists())
        cadence = CadenceRelanceEtape.cadence_pour(company)
        self.assertEqual(len(cadence), 5)
        self.assertTrue(CadenceRelanceEtape.objects.filter(company=company).exists())

    def test_cadence_pour_ignore_les_barreaux_inactifs(self):
        company = _company('cad-relance-inactif')
        CadenceRelanceEtape.seed_defaults(company)
        CadenceRelanceEtape.objects.filter(company=company, ordre=1).update(actif=False)
        cadence = CadenceRelanceEtape.cadence_pour(company)
        self.assertEqual(len(cadence), 4)


class CadenceRelanceEtapeAPITest(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='cad_admin', password='pw', role_legacy='admin',
            company=self.company)
        self.viewer = User.objects.create_user(
            username='cad_viewer', password='pw', role_legacy='utilisateur',
            company=self.company)
        self.api = _auth(self.admin)

    def test_admin_lists_seeded_cadence(self):
        CadenceRelanceEtape.seed_defaults(self.company)
        resp = self.api.get(CADENCE_URL)
        self.assertEqual(resp.status_code, 200)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 5)

    def test_viewer_can_read_but_not_write(self):
        CadenceRelanceEtape.seed_defaults(self.company)
        etape = CadenceRelanceEtape.objects.filter(company=self.company).first()
        viewer_api = _auth(self.viewer)
        self.assertEqual(viewer_api.get(CADENCE_URL).status_code, 200)
        resp = viewer_api.patch(
            f'{CADENCE_URL}{etape.id}/', {'libelle': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_edits_libelle_reste_company_scope(self):
        CadenceRelanceEtape.seed_defaults(self.company)
        etape = CadenceRelanceEtape.objects.filter(company=self.company).first()
        resp = self.api.patch(
            f'{CADENCE_URL}{etape.id}/', {'libelle': 'Relance perso'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        etape.refresh_from_db()
        self.assertEqual(etape.libelle, 'Relance perso')
        self.assertEqual(etape.company_id, self.company.id)

    def test_autre_societe_ne_voit_pas_la_cadence(self):
        other = _company('cad-relance-other', 'Cadence Relance Other')
        CadenceRelanceEtape.seed_defaults(self.company)
        CadenceRelanceEtape.seed_defaults(other)
        resp = self.api.get(CADENCE_URL)
        rows = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r['id'] for r in rows))
