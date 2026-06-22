"""Tests FG119 — plan d'amortissement (linéaire/dégressif) + dotations postées.

Couvre :

* Calendrier LINÉAIRE : base/durée par an, dernière année soldée exactement,
  cumul/valeur nette cohérents, Σ dotations = base.
* Calendrier DÉGRESSIF : taux dégressif = (100/durée) × coefficient marocain
  appliqué à la valeur nette résiduelle, bascule sur le linéaire en fin de plan,
  Σ dotations = base, première annuité > linéaire.
* Idempotence : re-générer ne duplique pas, préserve les dotations déjà postées.
* Posting : ``poster_dotation`` crée une écriture ÉQUILIBRÉE (débit classe 6 /
  crédit classe 28), idempotente, qui marque la dotation ``posted``.
* Verrou de période : poster dans une période verrouillée est REFUSÉ.
* Multi-société : isolation des plans/dotations entre deux sociétés ; l'API pose
  ``company`` côté serveur et renvoie 404 en cross-société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    DotationAmortissement, EcritureComptable, Immobilisation,
    PlanAmortissement,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_immo(company, **kwargs):
    defaults = dict(
        libelle='Camionnette',
        categorie=Immobilisation.Categorie.VEHICULE,
        cout=Decimal('100000'),
        taux_tva=Decimal('20.00'),
        date_acquisition=date(2026, 1, 1),
    )
    defaults.update(kwargs)
    return Immobilisation.objects.create(company=company, **defaults)


# ── Calcul du calendrier ────────────────────────────────────────────────────

class CalendrierLineaireTests(TestCase):
    def setUp(self):
        self.co = make_company('amort-lin', 'Amort Lin')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_lineaire_base_sur_duree(self):
        immo = make_immo(self.co, cout=Decimal('100000'))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        dotations = list(plan.dotations.order_by('annee'))
        self.assertEqual(len(dotations), 5)
        # 100000 / 5 = 20000 par an.
        for dot in dotations:
            self.assertEqual(dot.montant, Decimal('20000.00'))
        # Années consécutives à partir de la date de début.
        self.assertEqual([d.annee for d in dotations],
                         [2026, 2027, 2028, 2029, 2030])

    def test_lineaire_cumul_et_valeur_nette(self):
        immo = make_immo(self.co, cout=Decimal('100000'))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=4)
        dotations = list(plan.dotations.order_by('annee'))
        self.assertEqual(dotations[0].cumul, Decimal('25000.00'))
        self.assertEqual(dotations[0].valeur_nette, Decimal('75000.00'))
        self.assertEqual(dotations[-1].cumul, Decimal('100000.00'))
        self.assertEqual(dotations[-1].valeur_nette, Decimal('0.00'))

    def test_lineaire_derniere_annee_solde_arrondi(self):
        # 10000 / 3 = 3333,33 → la dernière année absorbe l'écart.
        immo = make_immo(self.co, cout=Decimal('10000'))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=3)
        dotations = list(plan.dotations.order_by('annee'))
        total = sum((d.montant for d in dotations), Decimal('0'))
        self.assertEqual(total, Decimal('10000.00'))
        self.assertEqual(dotations[-1].cumul, Decimal('10000.00'))


class CalendrierDegressifTests(TestCase):
    def setUp(self):
        self.co = make_company('amort-deg', 'Amort Deg')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_coefficient_marocain(self):
        self.assertEqual(services.coefficient_degressif_maroc(3), Decimal('1.5'))
        self.assertEqual(services.coefficient_degressif_maroc(4), Decimal('1.5'))
        self.assertEqual(services.coefficient_degressif_maroc(5), Decimal('2'))
        self.assertEqual(services.coefficient_degressif_maroc(6), Decimal('2'))
        self.assertEqual(services.coefficient_degressif_maroc(8), Decimal('3'))

    def test_degressif_premiere_annuite_superieure_au_lineaire(self):
        # Durée 5 → coefficient 2 → taux dégressif 40 %. 1re annuité = 40000 >
        # annuité linéaire 20000.
        immo = make_immo(self.co, cout=Decimal('100000'))
        plan = services.generer_plan_amortissement(
            immo, mode='degressif', duree_annees=5)
        self.assertEqual(plan.coefficient_degressif, Decimal('2'))
        dotations = list(plan.dotations.order_by('annee'))
        self.assertEqual(dotations[0].montant, Decimal('40000.00'))
        self.assertGreater(dotations[0].montant, Decimal('20000.00'))

    def test_degressif_solde_exactement_la_base(self):
        immo = make_immo(self.co, cout=Decimal('100000'))
        plan = services.generer_plan_amortissement(
            immo, mode='degressif', duree_annees=5)
        dotations = list(plan.dotations.order_by('annee'))
        total = sum((d.montant for d in dotations), Decimal('0'))
        self.assertEqual(total, Decimal('100000.00'))
        self.assertEqual(dotations[-1].valeur_nette, Decimal('0.00'))
        # Les annuités décroissent puis basculent sur le linéaire du résiduel.
        self.assertGreaterEqual(dotations[0].montant, dotations[1].montant)

    def test_degressif_coefficient_explicite(self):
        immo = make_immo(self.co, cout=Decimal('60000'))
        plan = services.generer_plan_amortissement(
            immo, mode='degressif', duree_annees=4,
            coefficient_degressif='1.5')
        self.assertEqual(plan.coefficient_degressif, Decimal('1.50'))
        total = sum((d.montant for d in plan.dotations.all()), Decimal('0'))
        self.assertEqual(total, Decimal('60000.00'))


# ── Idempotence ─────────────────────────────────────────────────────────────

class IdempotenceTests(TestCase):
    def setUp(self):
        self.co = make_company('amort-idem', 'Amort Idem')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_regenerer_ne_duplique_pas(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        n1 = DotationAmortissement.objects.filter(company=self.co).count()
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        n2 = DotationAmortissement.objects.filter(company=self.co).count()
        self.assertEqual(n1, n2)
        self.assertEqual(
            PlanAmortissement.objects.filter(company=self.co).count(), 1)

    def test_regenerer_preserve_dotation_postee(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        dot = plan.dotations.order_by('annee').first()
        services.poster_dotation(dot)
        dot.refresh_from_db()
        ecriture_id = dot.ecriture_id
        self.assertTrue(dot.posted)
        # Re-génération : la dotation postée reste liée à son écriture.
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        dot.refresh_from_db()
        self.assertTrue(dot.posted)
        self.assertEqual(dot.ecriture_id, ecriture_id)

    def test_reduire_duree_purge_dotations_non_postees(self):
        immo = make_immo(self.co, cout=Decimal('50000'))
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5)
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=3)
        self.assertEqual(
            DotationAmortissement.objects.filter(company=self.co).count(), 3)


# ── Posting au grand livre ──────────────────────────────────────────────────

class PostingTests(TestCase):
    def setUp(self):
        self.co = make_company('amort-post', 'Amort Post')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.immo = make_immo(self.co, cout=Decimal('100000'))
        self.plan = services.generer_plan_amortissement(
            self.immo, mode='lineaire', duree_annees=5)

    def test_poster_cree_ecriture_equilibree(self):
        dot = self.plan.dotations.order_by('annee').first()
        ecriture = services.poster_dotation(dot)
        self.assertTrue(ecriture.est_equilibree)
        self.assertEqual(ecriture.total_debit, Decimal('20000.00'))
        self.assertEqual(ecriture.total_credit, Decimal('20000.00'))
        # Débit sur un compte de classe 6, crédit sur un compte de classe 28.
        debits = [lig for lig in ecriture.lignes.all() if lig.debit]
        credits = [lig for lig in ecriture.lignes.all() if lig.credit]
        self.assertEqual(len(debits), 1)
        self.assertEqual(len(credits), 1)
        self.assertEqual(debits[0].compte.classe, 6)
        self.assertEqual(credits[0].compte.classe, 2)
        self.assertTrue(credits[0].compte.numero.startswith('28'))

    def test_poster_marque_dotation_postee(self):
        dot = self.plan.dotations.order_by('annee').first()
        services.poster_dotation(dot)
        dot.refresh_from_db()
        self.assertTrue(dot.posted)
        self.assertIsNotNone(dot.ecriture_id)

    def test_poster_idempotent(self):
        dot = self.plan.dotations.order_by('annee').first()
        e1 = services.poster_dotation(dot)
        e2 = services.poster_dotation(dot)
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co,
                source_type='dotation_amortissement').count(), 1)

    def test_poster_dans_periode_verrouillee_refuse(self):
        dot = self.plan.dotations.order_by('annee').first()
        # Période couvrant le 31/12/2026 (date imputée à la dotation 2026).
        periode = services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 12, 31),
            type_periode='exercice', libelle='Exercice 2026')
        services.cloturer_periode(periode)
        with self.assertRaises(ValidationError):
            services.poster_dotation(dot)
        dot.refresh_from_db()
        self.assertFalse(dot.posted)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co,
                source_type='dotation_amortissement').count(), 0)


# ── Isolation multi-société ─────────────────────────────────────────────────

class IsolationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('amort-a', 'Amort A')
        self.co_b = make_company('amort-b', 'Amort B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)

    def test_plans_isoles_par_societe(self):
        immo_a = make_immo(self.co_a, cout=Decimal('10000'))
        immo_b = make_immo(self.co_b, cout=Decimal('20000'))
        services.generer_plan_amortissement(
            immo_a, mode='lineaire', duree_annees=2)
        services.generer_plan_amortissement(
            immo_b, mode='lineaire', duree_annees=2)
        self.assertEqual(
            PlanAmortissement.objects.filter(company=self.co_a).count(), 1)
        self.assertEqual(
            DotationAmortissement.objects.filter(
                company=self.co_a).count(), 2)
        self.assertEqual(
            DotationAmortissement.objects.filter(
                company=self.co_b).count(), 2)


# ── API ─────────────────────────────────────────────────────────────────────

class AmortissementApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('amort-api-a', 'Amort API A')
        self.co_b = make_company('amort-api-b', 'Amort API B')
        self.user_a = make_user(self.co_a, 'amort-user-a')
        self.user_b = make_user(self.co_b, 'amort-user-b')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.immo_a = make_immo(self.co_a, cout=Decimal('100000'))

    def _plan_url(self, immo):
        return (f'/api/django/compta/immobilisations/{immo.id}/'
                'plan-amortissement/')

    def test_generer_plan_via_api_pose_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self._plan_url(self.immo_a),
                        {'mode': 'lineaire', 'duree_annees': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        plan = PlanAmortissement.objects.get(id=resp.data['id'])
        self.assertEqual(plan.company, self.co_a)  # posée côté serveur.
        self.assertEqual(len(resp.data['dotations']), 5)

    def test_get_plan_404_si_absent(self):
        api = auth(self.user_a)
        resp = api.get(self._plan_url(self.immo_a))
        self.assertEqual(resp.status_code, 404)

    def test_plan_cross_company_404(self):
        immo_b = make_immo(self.co_b, cout=Decimal('50000'))
        api_a = auth(self.user_a)
        resp = api_a.post(self._plan_url(immo_b),
                          {'mode': 'lineaire', 'duree_annees': 5},
                          format='json')
        self.assertEqual(resp.status_code, 404)

    def test_poster_dotation_via_api(self):
        plan = services.generer_plan_amortissement(
            self.immo_a, mode='lineaire', duree_annees=5)
        dot = plan.dotations.order_by('annee').first()
        api = auth(self.user_a)
        resp = api.post(
            f'/api/django/compta/dotations/{dot.id}/poster/', format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data['ecriture_id'])
        dot.refresh_from_db()
        self.assertTrue(dot.posted)

    def test_dotations_isolees_dans_liste(self):
        plan_a = services.generer_plan_amortissement(
            self.immo_a, mode='lineaire', duree_annees=2)
        immo_b = make_immo(self.co_b, cout=Decimal('50000'))
        services.generer_plan_amortissement(
            immo_b, mode='lineaire', duree_annees=2)
        api_a = auth(self.user_a)
        resp = api_a.get('/api/django/compta/dotations/')
        self.assertEqual(resp.status_code, 200)
        plan_ids = {r['plan'] for r in rows(resp)}
        self.assertTrue(plan_ids <= {plan_a.id})

    def test_poster_dotation_cross_company_404(self):
        plan_b = services.generer_plan_amortissement(
            make_immo(self.co_b, cout=Decimal('50000')),
            mode='lineaire', duree_annees=2)
        dot_b = plan_b.dotations.first()
        api_a = auth(self.user_a)
        resp = api_a.post(
            f'/api/django/compta/dotations/{dot_b.id}/poster/', format='json')
        self.assertEqual(resp.status_code, 404)

    def test_acces_refuse_role_normal(self):
        normal = make_user(self.co_a, 'amort-normal', role='normal')
        api = auth(normal)
        resp = api.get('/api/django/compta/dotations/')
        self.assertEqual(resp.status_code, 403)
