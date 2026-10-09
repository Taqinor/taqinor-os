"""ACHT13 (C-ACHT-011) — l'engagement budgétaire d'une demande d'achat est
libéré sur TOUTE sortie vers « refusée » (`refuser`, `rejeter-etape`,
`decider_demande_achat(approuver=False)`) : l'effet vit au point d'écriture
du statut (`appliquer_statut_document`).

Rejoue CACH-6 : refus par étape → restant 400 au lieu de 1 000, la 2e DA
de 600 est refusée « il reste 400.00 MAD ».

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_budget_refus"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import services
from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RegleApprobationAchat,
)
from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    AchatsParametres, BudgetDepartement, EngagementBudget,
)

User = get_user_model()
BASE = '/api/django/installations'


class BudgetRefusTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht13', defaults={'nom': 'Co ACHT13'})
        self.demandeur = User.objects.create_user(
            username='resp-acht13', password='x', company=self.company,
            role_legacy='responsable')
        self.approbateur = User.objects.create_user(
            username='admin-acht13', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.demandeur)}'))
        params = AchatsParametres.for_company(self.company)
        params.budget_departement_actif = True
        params.save(update_fields=['budget_departement_actif'])
        self.budget = BudgetDepartement.objects.create(
            company=self.company,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=timezone.localdate().year, montant_alloue=1000)
        self._n = 0

    def _da(self, montant=600):
        self._n += 1
        da = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-ACHT13-{self._n}',
            objet='Budget', created_by=self.demandeur)
        DemandeAchatLigne.objects.create(
            demande=da, designation='Article', quantite=1,
            prix_estime=montant)
        r = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(r.status_code, 200, r.data)
        da.refresh_from_db()
        return da

    def _restant(self):
        return stock_selectors.consommation_budget(self.budget)['restant']

    def _assert_libere(self, da):
        engagement = EngagementBudget.objects.get(demande_achat=da)
        self.assertEqual(engagement.statut, EngagementBudget.Statut.LIBERE)
        self.assertEqual(self._restant(), Decimal('1000.00'))
        # L'enveloppe rendue permet une seconde demande de 600.
        self._da(600)

    def test_rejeter_etape_libere(self):
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Une étape', montant_min=0,
            nombre_approbateurs=1)
        da = self._da(600)
        self.assertEqual(self._restant(), Decimal('400.00'))
        etape = da.etapes_approbation.filter(
            statut=EtapeApprobationAchat.Statut.EN_ATTENTE).first()
        self.assertIsNotNone(etape)
        services.rejeter_etape_achat(etape, approbateur=self.approbateur,
                                     commentaire='Non')
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self._assert_libere(da)

    def test_decider_refus_libere(self):
        da = self._da(600)
        self.assertEqual(self._restant(), Decimal('400.00'))
        services.decider_demande_achat(
            da, approuver=False, user=self.approbateur, motif_refus='Non')
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)
        self._assert_libere(da)

    def test_refuser_temoin(self):
        da = self._da(600)
        r = self.api.post(f'{BASE}/demandes-achat/{da.pk}/refuser/',
                          {'motif_refus': 'Non'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(EngagementBudget.objects.filter(
            demande_achat=da).count(), 1)
        self._assert_libere(da)
