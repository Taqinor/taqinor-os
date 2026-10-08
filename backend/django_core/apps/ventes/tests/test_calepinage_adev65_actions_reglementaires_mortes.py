"""ADEV65 (C-ADEV-054) — les trois actions réglementaires sans appelant de
production sont RETIRÉES : ``generer-checklist`` et ``generer-schema`` (dossier
réglementaire) et ``generer-declaration`` (régularisation 82-21, qui avançait
le statut sur une chaîne libre ``declaration_pdf`` jamais relue). POST sur
chacune → 404, rien n'est écrit.

Test-du-test : remettre une des actions dans ``views/regulatory.py`` ⇒
``test_routes_absentes`` la NOMME (sous-test par route).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_calepinage_adev65_actions_reglementaires_mortes"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import (
    Devis, DossierChecklistItem, RegulatoryDossier, Regularisation8221)
from apps.ventes.views.regulatory import (
    Regularisation8221ViewSet, RegulatoryDossierViewSet)
from authentication.models import Company

User = get_user_model()

ACTIONS_RETIREES = ('generer_checklist', 'generer_schema',
                    'generer_declaration')


class ActionsMortesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ADEV65 Co', slug='adev65-co')
        self.user = User.objects.create_user(
            username='adev65_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV65',
            email='adev65@example.test', telephone='+212600006500')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV65-1', client=client,
            statut='accepte', created_by=self.user)
        self.dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt')
        self.regul = Regularisation8221.objects.create(
            company=self.company, devis=self.devis,
            regime_8221='declaration_bt')

    def test_routes_absentes(self):
        routes = []
        for prefixe in ('/api/django/ventes/', '/api/v1/ventes/'):
            routes += [
                f'{prefixe}dossiers-reglementaires/{self.dossier.id}'
                '/generer-checklist/',
                f'{prefixe}dossiers-reglementaires/{self.dossier.id}'
                '/generer-schema/',
                f'{prefixe}regularisations-8221/{self.regul.id}'
                '/generer-declaration/',
            ]
        for url in routes:
            with self.subTest(route=url):
                resp = self.api.post(
                    url, {'declaration_pdf': 'declarations/x.pdf'},
                    format='json')
                self.assertEqual(resp.status_code, 404, url)
        # Rien n'est écrit : aucune pièce semée, statut inchangé.
        self.assertFalse(DossierChecklistItem.objects.filter(
            dossier=self.dossier).exists())
        self.regul.refresh_from_db()
        self.assertEqual(self.regul.statut, 'a_regulariser')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'accepte')

    def test_viewsets_sans_les_actions(self):
        for viewset in (RegulatoryDossierViewSet, Regularisation8221ViewSet):
            for nom in ACTIONS_RETIREES:
                with self.subTest(viewset=viewset.__name__, action=nom):
                    self.assertFalse(hasattr(viewset, nom))
