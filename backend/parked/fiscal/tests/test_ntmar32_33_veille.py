"""NTMAR32/33 — Veille réglementaire in-app + lien actionnable.

Critères : une entrée de veille apparaît filtrable par domaine avec sa date
d'effet ; une veille « taux TVA modifié » propose un lien direct vers le
paramètre concerné et marque son impact traité une fois revu."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.fiscal.models import VeilleReglementaire
from apps.fiscal.services import marquer_impact_veille_traite

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VeilleFiltreDomaineTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-veille', 'Fiscal Veille')
        self.user = make_user(self.company, 'fiscal-veille-user')
        self.api = auth(self.user)

    def test_filter_by_domaine(self):
        VeilleReglementaire.objects.create(
            company=self.company, domaine=VeilleReglementaire.Domaine.TVA,
            titre='Taux TVA modifié')
        VeilleReglementaire.objects.create(
            company=self.company, domaine=VeilleReglementaire.Domaine.CNSS,
            titre='Nouveau taux CNSS')
        resp = self.api.get('/api/django/fiscal/veille/?domaine=tva')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['titre'], 'Taux TVA modifié')

    def test_global_entry_visible_to_all_companies(self):
        VeilleReglementaire.objects.create(
            company=None, domaine=VeilleReglementaire.Domaine.EINVOICING,
            titre='Nouvelle norme e-invoicing DGI')
        resp = self.api.get('/api/django/fiscal/veille/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertTrue(
            any(row['titre'] == 'Nouvelle norme e-invoicing DGI' for row in data))


class ImpactActionnableTests(TestCase):
    def setUp(self):
        self.company = make_company('fiscal-impact', 'Fiscal Impact')

    def test_impact_link_and_mark_treated(self):
        veille = VeilleReglementaire.objects.create(
            company=self.company, domaine=VeilleReglementaire.Domaine.TVA,
            titre='Taux TVA modifié',
            parametre_cible='CompanyProfile.tva_defaut')
        self.assertFalse(veille.impact_traite)
        marquer_impact_veille_traite(veille)
        veille.refresh_from_db()
        self.assertTrue(veille.impact_traite)
        self.assertEqual(veille.parametre_cible, 'CompanyProfile.tva_defaut')
