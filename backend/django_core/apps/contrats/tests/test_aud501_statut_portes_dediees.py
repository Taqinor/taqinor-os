"""AUD501 — la machine d'états du Contrat n'est plus un décor.

``Contrat.statut`` était absent de ``read_only_fields`` alors que le docstring
de ``ContratViewSet.perform_update`` affirmait le contraire : un PATCH brut du
corps posait « signe » sur un contrat en approbation SANS qu'aucune
``SignatureContrat`` n'existe.

Et l'action générique ``changer-statut`` ne faisait que traverser
``machine_etats`` : elle n'appelait JAMAIS ``signer_contrat`` (seul créateur
d'une ``SignatureContrat``, de l'événement ``contrat_signe`` et de la
``VersionContrat`` figée), ni ``resilier_contrat`` (seul créateur d'une
``Resiliation`` et de l'événement ``contrat_resilie``, qui désactive la
maintenance SAV). Un contrat pouvait donc être « signé » sans signature et
« résilié » sans résiliation.
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats.models import Contrat, PartieContrat, SignatureContrat
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/contrats/contrats'


class TestStatutPortesDediees(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'aud501-{n}', nom=f'AUD501 Co {n}')
        self.user = User.objects.create_user(
            username=f'aud501-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _contrat(self, statut=Contrat.Statut.EN_APPROBATION, parties=2):
        contrat = Contrat.objects.create(
            company=self.company, created_by=self.user,
            reference=f'CTR-AUD501-{next(_seq)}', objet='Maintenance',
            statut=statut, montant=Decimal('12000'))
        for i in range(parties):
            PartieContrat.objects.create(
                company=self.company, contrat=contrat,
                nom=f'Partie {i}', ordre=i)
        return contrat

    # ── La porte GÉNÉRIQUE : le PATCH brut ────────────────────────────────

    def test_patch_brut_du_statut_est_ignore(self):
        """ROUGE avant le correctif : le contrat passait « signe » sans
        AUCUNE SignatureContrat."""
        contrat = self._contrat()
        resp = self.api.patch(
            f'{BASE}/{contrat.id}/', {'statut': 'signe'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.EN_APPROBATION)
        self.assertFalse(
            SignatureContrat.objects.filter(contrat=contrat).exists())

    # ── La porte GÉNÉRIQUE : l'action changer-statut ──────────────────────

    def test_changer_statut_refuse_signe(self):
        contrat = self._contrat()
        resp = self.api.post(
            f'{BASE}/{contrat.id}/changer-statut/',
            {'statut': 'signe'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('signer', resp.data['detail'])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.EN_APPROBATION)

    def test_changer_statut_refuse_resilie_sans_resiliation(self):
        """Parité sémantique (patron AUD316) : la cible RESILIE échoue tant
        qu'aucune Resiliation n'est créée dans le même appel."""
        from apps.contrats.models import Resiliation
        contrat = self._contrat(statut=Contrat.Statut.ACTIF)
        resp = self.api.post(
            f'{BASE}/{contrat.id}/changer-statut/',
            {'statut': 'resilie'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('resilier', resp.data['detail'])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)
        self.assertFalse(
            Resiliation.objects.filter(contrat=contrat).exists())

    def test_les_transitions_administratives_passent_toujours(self):
        """Un contrat BROUILLON part en approbation, un ACTIF se suspend :
        ces transitions n'ont pas de porte dédiée, elles restent ici."""
        contrat = self._contrat(statut=Contrat.Statut.BROUILLON)
        resp = self.api.post(
            f'{BASE}/{contrat.id}/changer-statut/',
            {'statut': 'en_approbation'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.EN_APPROBATION)

        actif = self._contrat(statut=Contrat.Statut.ACTIF)
        resp = self.api.post(
            f'{BASE}/{actif.id}/changer-statut/',
            {'statut': 'suspendu'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        actif.refresh_from_db()
        self.assertEqual(actif.statut, Contrat.Statut.SUSPENDU)

    # ── La porte DÉDIÉE fonctionne toujours ──────────────────────────────

    def test_la_porte_dediee_de_resiliation_fonctionne_et_cree_la_resiliation(
            self):
        from apps.contrats.models import Resiliation
        contrat = self._contrat(statut=Contrat.Statut.ACTIF)
        resp = self.api.post(
            f'{BASE}/{contrat.id}/resilier/',
            {'motif': 'Fin de collaboration'}, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.RESILIE)
        self.assertTrue(
            Resiliation.objects.filter(contrat=contrat).exists())

    def test_mrr_baisse_apres_resiliation(self):
        """`mrr_contrats` filtre bien sur le statut du contrat : un contrat
        résilié cesse de compter comme revenu récurrent SAIN."""
        from apps.contrats.models import EcheancierContrat
        from apps.contrats.selectors import mrr_contrats
        contrat = self._contrat(statut=Contrat.Statut.ACTIF)
        EcheancierContrat.objects.create(
            company=self.company, contrat=contrat,
            montant_total=Decimal('1200'),
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            statut=EcheancierContrat.Statut.ACTIF,
            facturation_active=True)
        avant = mrr_contrats(self.company)
        self.assertEqual(avant, Decimal('1200.00'))

        self.api.post(f'{BASE}/{contrat.id}/resilier/',
                      {'motif': 'Test'}, format='json')
        self.assertEqual(mrr_contrats(self.company), Decimal('0.00'))
