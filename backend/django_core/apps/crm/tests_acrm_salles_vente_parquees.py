"""ACRM65 — salles de vente PARQUÉES derrière le réglage société
``salles_vente_actif`` (décision fondateur D-ACRM-6 (ii)=(b), 09/10/2026).

Nouveau fichier car : aucun module ne teste un réglage d'activation des salles.

Éteint (défaut d'une société neuve) : ``salles-vente/`` rend une liste vide,
détail / analytics / items 404, le lien public par jeton répond 404, aucune
vue journalisée, aucun signal d'intérêt émis — et la salle reste en base.
Allumé : comportement d'avant. Source réelle : vues et signal réels, aucun
mock. Test-du-test : ignorer le réglage ⇒ test_eteint_jeton_404 échoue.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, SalleVente, SalleVenteVue
from apps.parametres.models import CompanyProfile

User = get_user_model()

BASE = '/api/django/crm/'


class SallesVenteParqueesTests(TestCase):

    def setUp(self):
        self.eteinte = Company.objects.create(
            nom='Salles éteintes', slug='acrm65-eteinte')
        CompanyProfile.objects.get_or_create(company=self.eteinte)
        self.allumee = Company.objects.create(
            nom='Salles allumées', slug='acrm65-allumee')
        CompanyProfile.objects.update_or_create(
            company=self.allumee, defaults={'salles_vente_actif': True})
        self.u_eteinte = User.objects.create_user(
            username='acrm65-e', password='x', role_legacy='admin',
            company=self.eteinte)
        self.u_allumee = User.objects.create_user(
            username='acrm65-a', password='x', role_legacy='admin',
            company=self.allumee)
        self.salle_e = self._salle(self.eteinte, self.u_eteinte)
        self.salle_a = self._salle(self.allumee, self.u_allumee)

    def _salle(self, company, user):
        lead = Lead.objects.create(
            company=company, nom='Prospect salle', owner=user,
            stage=stages.QUOTE_SENT)
        return SalleVente.objects.create(
            company=company, lead=lead, titre='Salle', created_by=user)

    def _api(self, user=None):
        api = APIClient()
        if user is not None:
            api.credentials(
                HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_une_societe_neuve_a_le_reglage_eteint(self):
        profil = CompanyProfile.objects.get(company=self.eteinte)
        self.assertFalse(profil.salles_vente_actif)

    def test_eteint_liste_vide(self):
        resp = self._api(self.u_eteinte).get(f'{BASE}salles-vente/')
        self.assertEqual(resp.status_code, 200, resp.content[:200])
        lignes = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(list(lignes), [])

    def test_eteint_detail_analytics_items_404(self):
        api = self._api(self.u_eteinte)
        pk = self.salle_e.pk
        self.assertEqual(api.get(f'{BASE}salles-vente/{pk}/').status_code, 404)
        self.assertEqual(
            api.get(f'{BASE}salles-vente/{pk}/analytics/').status_code, 404)
        self.assertEqual(api.post(
            f'{BASE}salles-vente/{pk}/items/',
            {'type': 'lien', 'titre': 'x', 'reference': 'https://exemple.ma'},
            format='json').status_code, 404)

    def test_eteint_jeton_404(self):
        resp = self._api().get(f'{BASE}salle-vente/{self.salle_e.token}/')
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(SalleVenteVue.objects.filter(salle=self.salle_e).exists())

    def test_eteint_aucun_signal(self):
        """Trois consultations : aucune vue journalisée, aucune note
        « signal d'intérêt fort » (le seul effet du signal NTCRM27)."""
        api = self._api()
        for _ in range(3):
            api.get(f'{BASE}salle-vente/{self.salle_e.token}/',
                    REMOTE_ADDR='10.0.0.%d' % _)
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.salle_e.lead,
            body__startswith="signal d'intérêt fort").exists())

    def test_eteint_la_salle_reste_en_base(self):
        self._api(self.u_eteinte).get(f'{BASE}salles-vente/')
        self._api().get(f'{BASE}salle-vente/{self.salle_e.token}/')
        self.assertTrue(SalleVente.objects.filter(pk=self.salle_e.pk).exists())

    def test_allume_inchange(self):
        api = self._api(self.u_allumee)
        resp = api.get(f'{BASE}salles-vente/')
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([s['id'] for s in lignes], [self.salle_a.pk])
        self.assertEqual(
            api.get(f'{BASE}salles-vente/{self.salle_a.pk}/').status_code, 200)
        resp = self._api().get(f'{BASE}salle-vente/{self.salle_a.token}/')
        self.assertEqual(resp.status_code, 200, resp.content[:200])
        self.assertTrue(SalleVenteVue.objects.filter(salle=self.salle_a).exists())
