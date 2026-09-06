"""AUD528 — la liste des contrats ne coûte plus 2N requêtes.

``ContratViewSet.queryset`` était ``Contrat.objects.all()`` — le SEUL des ~15
ViewSets du fichier sans ``select_related``, alors que ``ContratSerializer``
lit ``responsable`` (FK) sur CHAQUE ligne. Et ``get_client_nom`` appelait
``crm_selectors.client_label`` — une requête DB par ligne — sans aucun cache
par page.
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats.models import Contrat
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/contrats/contrats'


class TestBudgetRequetesListeContrats(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud528-{n}', nom=f'AUD528 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud528-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _contrat(self):
        n = next(_seq)
        responsable = User.objects.create_user(
            username=f'aud528-resp-{n}', password='x', company=self.company)
        client = Client.objects.create(
            company=self.company, nom=f'Client {n}', prenom='AUD528',
            telephone=f'+21260000{n:04d}')
        return Contrat.objects.create(
            company=self.company, created_by=self.user,
            reference=f'CTR-AUD528-{n}', objet='Maintenance',
            statut=Contrat.Statut.ACTIF, montant=Decimal('12000'),
            responsable=responsable, client_id=client.id)

    def _cout(self, n_nouveaux):
        for _ in range(n_nouveaux):
            self._contrat()
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(f'{BASE}/')
            self.assertEqual(resp.status_code, 200, resp.content)
        return len(ctx.captured_queries), resp

    def test_budget_independant_du_nombre_de_contrats(self):
        """ROUGE avant le correctif : ~2 requêtes de plus PAR contrat."""
        cout_1, _ = self._cout(1)
        cout_5, _ = self._cout(4)
        self.assertEqual(
            cout_1, cout_5,
            f'N+1 liste contrats : {cout_1} requêtes pour 1 contrat, '
            f'{cout_5} pour 5.')

    def test_les_libelles_rendus_sont_inchanges(self):
        """Le cache ne change AUCUN libellé : la source reste le sélecteur
        cross-app de crm."""
        contrat = self._contrat()
        _, resp = self._cout(0)
        ligne = next(r for r in resp.data.get('results', resp.data)
                     if r['id'] == contrat.id)
        self.assertEqual(ligne['responsable_nom'],
                         contrat.responsable.username)
        from apps.crm import selectors as crm_selectors
        self.assertEqual(
            ligne['client_nom'],
            crm_selectors.client_label(self.company, contrat.client_id))

    def test_deux_contrats_du_meme_client_ne_paient_qu_une_lecture(self):
        client = Client.objects.create(
            company=self.company, nom='Partagé', prenom='AUD528',
            telephone='+212600009999')
        for _ in range(3):
            n = next(_seq)
            Contrat.objects.create(
                company=self.company, created_by=self.user,
                reference=f'CTR-AUD528-{n}', objet='Maintenance',
                statut=Contrat.Statut.ACTIF, client_id=client.id)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get(f'{BASE}/')
            self.assertEqual(resp.status_code, 200, resp.content)
        lectures_client = [
            q for q in ctx.captured_queries
            if 'crm_client' in q['sql'].lower()]
        self.assertLessEqual(
            len(lectures_client), 1,
            'le libellé client est relu une fois par contrat au lieu d\'être '
            'mémoïsé par page')
