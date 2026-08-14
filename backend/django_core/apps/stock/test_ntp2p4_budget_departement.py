"""
NTP2P4 — Budget d'engagement par département avec blocage dur.

CRITÈRE D'ACCEPTATION : soumettre une demande d'achat qui dépasse le budget
restant du département est REJETÉE (400) tant qu'aucune dérogation n'est
approuvée (règle d'approbation ``autorise_depassement_budget``, NTP2P2).

Couvre aussi : le no-op total quand l'interrupteur est OFF (défaut =
comportement historique), la résolution mensuel > annuel, la consommation
(engagé / réalisé / restant), la libération sur refus, la consommation à
l'émission du BCF, et le scope société.

Run :
    python manage.py test apps.stock.test_ntp2p4_budget_departement -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    DemandeAchat, DemandeAchatLigne, RegleApprobationAchat,
)
from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    AchatsParametres, BudgetDepartement, EngagementBudget,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'
STOCK = '/api/django/stock'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p4-co-{n}', defaults={'nom': f'NTP2P4 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_departement(company, nom='Achats'):
    from apps.rh.models import Departement
    return Departement.objects.create(company=company, nom=nom)


def rattacher(company, user, departement):
    """Crée le dossier employé qui rattache l'utilisateur au département."""
    from apps.rh.models import DossierEmploye
    return DossierEmploye.objects.create(
        company=company, user=user, departement=departement,
        matricule=f'M{next(_seq):04d}', nom=f'Employe{next(_seq)}',
        prenom='Test')


def make_demande(company, user, *, montant):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-BUD-{next(_seq):04d}',
        objet='Réquisition budget', created_by=user)
    DemandeAchatLigne.objects.create(
        demande=da, designation='Article', quantite=1, prix_estime=montant)
    return da


class BudgetInactifTests(TestCase):
    """Non-régression : sans l'interrupteur, aucun contrôle budgétaire."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dept = make_departement(self.company)
        rattacher(self.company, self.user, self.dept)
        BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=timezone.localdate().year, montant_alloue=1000)

    def test_soumission_hors_budget_passe_quand_le_controle_est_off(self):
        da = make_demande(self.company, self.user, montant=99999)
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], DemandeAchat.Statut.SOUMISE)
        self.assertEqual(EngagementBudget.objects.count(), 0)

    def test_reglage_off_par_defaut(self):
        params = AchatsParametres.for_company(self.company)
        self.assertFalse(params.budget_departement_actif)
        self.assertFalse(
            stock_selectors.budget_departement_actif(self.company))


class BudgetActifTests(TestCase):
    """Blocage dur quand l'interrupteur est activé."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dept = make_departement(self.company)
        rattacher(self.company, self.user, self.dept)
        params = AchatsParametres.for_company(self.company)
        params.budget_departement_actif = True
        params.save(update_fields=['budget_departement_actif'])
        self.budget = BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=timezone.localdate().year, montant_alloue=10000)

    def test_soumission_dans_le_budget_engage_le_montant(self):
        da = make_demande(self.company, self.user, montant=4000)
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        engagement = EngagementBudget.objects.get(demande_achat=da)
        self.assertEqual(engagement.montant, Decimal('4000.00'))
        self.assertEqual(engagement.statut, EngagementBudget.Statut.ACTIF)
        self.assertEqual(engagement.company_id, self.company.id)

    def test_soumission_hors_budget_refusee_400(self):
        """CRITÈRE D'ACCEPTATION."""
        make_demande(self.company, self.user, montant=8000)
        premiere = DemandeAchat.objects.latest('id')
        self.api.post(f'{BASE}/demandes-achat/{premiere.pk}/soumettre/')

        da = make_demande(self.company, self.user, montant=5000)
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Budget', resp.data['detail'])
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.BROUILLON)
        self.assertFalse(
            EngagementBudget.objects.filter(demande_achat=da).exists())

    def test_derogation_par_regle_approbation_laisse_passer(self):
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Dérogation direction',
            montant_min=1000, nombre_approbateurs=2,
            autorise_depassement_budget=True)
        make_demande(self.company, self.user, montant=8000)
        premiere = DemandeAchat.objects.latest('id')
        self.api.post(f'{BASE}/demandes-achat/{premiere.pk}/soumettre/')

        da = make_demande(self.company, self.user, montant=5000)
        resp = self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.SOUMISE)
        # La dérogation part en approbation (2 étapes), jamais en silence.
        self.assertEqual(da.etapes_approbation.count(), 2)

    def test_refus_libere_lenveloppe(self):
        da = make_demande(self.company, self.user, montant=9000)
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/refuser/',
                      {'motif_refus': 'Non'}, format='json')
        engagement = EngagementBudget.objects.get(demande_achat=da)
        self.assertEqual(engagement.statut, EngagementBudget.Statut.LIBERE)
        detail = stock_selectors.consommation_budget(self.budget)
        self.assertEqual(detail['restant'], Decimal('10000.00'))

    def test_resoumission_ne_double_pas_lengagement(self):
        da = make_demande(self.company, self.user, montant=4000)
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.api.post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(
            EngagementBudget.objects.filter(demande_achat=da).count(), 1)

    def test_sans_departement_aucun_controle(self):
        """Un demandeur sans dossier RH n'est jamais bloqué (no-op)."""
        orphelin = make_user(self.company)
        da = make_demande(self.company, orphelin, montant=99999)
        resp = auth(orphelin).post(
            f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)

    def test_departement_sans_budget_aucun_controle(self):
        autre_dept = make_departement(self.company, nom='Technique')
        user = make_user(self.company)
        rattacher(self.company, user, autre_dept)
        da = make_demande(self.company, user, montant=99999)
        resp = auth(user).post(f'{BASE}/demandes-achat/{da.pk}/soumettre/')
        self.assertEqual(resp.status_code, 200)


class ResolutionEtConsommationTests(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dept = make_departement(self.company)
        self.annee = timezone.localdate().year
        self.mois = timezone.localdate().month

    def test_budget_mensuel_prime_sur_annuel(self):
        BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=self.annee, montant_alloue=100000)
        mensuel = BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.MENSUELLE,
            annee=self.annee, mois=self.mois, montant_alloue=5000)
        resolu = stock_selectors.resoudre_budget_departement(
            self.company, self.dept.pk)
        self.assertEqual(resolu.pk, mensuel.pk)

    def test_consommation_engage_realise_restant(self):
        budget = BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=self.annee, montant_alloue=10000)
        EngagementBudget.objects.create(
            company=self.company, budget=budget, montant=3000,
            statut=EngagementBudget.Statut.ACTIF)
        EngagementBudget.objects.create(
            company=self.company, budget=budget, montant=2000,
            statut=EngagementBudget.Statut.CONSOMME)
        EngagementBudget.objects.create(
            company=self.company, budget=budget, montant=9000,
            statut=EngagementBudget.Statut.LIBERE)
        detail = stock_selectors.consommation_budget(budget)
        self.assertEqual(detail['engage'], Decimal('3000.00'))
        self.assertEqual(detail['realise'], Decimal('2000.00'))
        self.assertEqual(detail['restant'], Decimal('5000.00'))
        self.assertEqual(detail['taux_consommation_pct'], 50.0)

    def test_endpoint_consommation(self):
        budget = BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=self.annee, montant_alloue=8000)
        EngagementBudget.objects.create(
            company=self.company, budget=budget, montant=2000,
            statut=EngagementBudget.Statut.ACTIF)
        resp = self.api.get(
            f'{STOCK}/budgets-departement/{budget.pk}/consommation/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.data['engage']), '2000.00')
        self.assertEqual(str(resp.data['restant']), '6000.00')

    def test_endpoint_disponible_simulateur(self):
        """NTP2P23 — simulation LECTURE SEULE, aucun engagement posé."""
        params = AchatsParametres.for_company(self.company)
        params.budget_departement_actif = True
        params.save(update_fields=['budget_departement_actif'])
        BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=self.annee, montant_alloue=4000)
        resp = self.api.get(f'{STOCK}/budgets-departement/disponible/', {
            'departement': self.dept.pk, 'montant': '5000'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['controle_actif'])
        self.assertFalse(resp.data['suffisant'])
        self.assertEqual(str(resp.data['montant_manquant']), '1000.00')
        self.assertEqual(EngagementBudget.objects.count(), 0)

    def test_scope_societe_sur_les_budgets(self):
        autre = make_company()
        dept_autre = make_departement(autre)
        BudgetDepartement.objects.create(
            company=autre, departement=dept_autre,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=self.annee, montant_alloue=1)
        BudgetDepartement.objects.create(
            company=self.company, departement=self.dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=self.annee, montant_alloue=2)
        resp = self.api.get(f'{STOCK}/budgets-departement/')
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 1)
        self.assertEqual(str(data[0]['montant_alloue']), '2.00')

    def test_company_du_corps_ignoree(self):
        autre = make_company()
        resp = self.api.post(f'{STOCK}/budgets-departement/', {
            'departement': self.dept.pk, 'periodicite': 'annuelle',
            'annee': self.annee, 'mois': 0, 'montant_alloue': '500.00',
            'company': autre.pk,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        budget = BudgetDepartement.objects.get(pk=resp.data['id'])
        self.assertEqual(budget.company_id, self.company.id)

    def test_departement_dune_autre_societe_rejete(self):
        autre = make_company()
        dept_autre = make_departement(autre)
        resp = self.api.post(f'{STOCK}/budgets-departement/', {
            'departement': dept_autre.pk, 'periodicite': 'annuelle',
            'annee': self.annee, 'mois': 0, 'montant_alloue': '500.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_budget_mensuel_exige_un_mois(self):
        resp = self.api.post(f'{STOCK}/budgets-departement/', {
            'departement': self.dept.pk, 'periodicite': 'mensuelle',
            'annee': self.annee, 'mois': 0, 'montant_alloue': '500.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_engagements_en_lecture_seule(self):
        resp = self.api.post(f'{STOCK}/engagements-budget/',
                             {'montant': '10.00'}, format='json')
        self.assertIn(resp.status_code, (403, 405))
