"""Tests FG140 — Aide au calcul de l'IS (impôt sur les sociétés).

Couvre : l'IS au barème progressif marocain (10 / 20 / 31 % par tranche), le
plancher de la cotisation minimale (CM), l'estimation de l'IS dû depuis le CPC
de l'exercice (résultat fiscal = résultat comptable ± réintégrations/déductions),
l'échéancier des 4 acomptes provisionnels (25 % chacun, échéances 3e/6e/9e/12e
mois), la régularisation (IS dû − acomptes), l'isolation multi-société et
l'endpoint ``aide-is`` (admin-gated) + son export CSV. Tout se déduit du grand
livre — aucune dépendance cross-app. Aucune écriture n'est créée par l'aide.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import ExerciceComptable, Journal

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


def make_exercice(company, annee=2026):
    return ExerciceComptable.objects.create(
        company=company, libelle=f'Exercice {annee}',
        date_debut=date(annee, 1, 1), date_fin=date(annee, 12, 31))


def _resultat(company, produits, charges, *, jour=date(2026, 6, 15)):
    """Passe une écriture VTE produisant un résultat (produits 7121, charges 6111).

    Crédit 7121 = produits, débit 6111 = charges, l'équilibre passe par la
    trésorerie (5141). Résultat comptable du CPC = produits − charges.
    """
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    lignes = [
        {'compte': services.get_compte(company, '6111'),
         'debit': Decimal(charges), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '5141'),
         'debit': Decimal(produits), 'credit': Decimal('0')},
        {'compte': services.get_compte(company, '7121'),
         'debit': Decimal('0'), 'credit': Decimal(produits)},
        {'compte': services.get_compte(company, '4411'),
         'debit': Decimal('0'), 'credit': Decimal(charges)},
    ]
    return services.creer_ecriture(
        company, journal, jour, 'Résultat FG140', lignes)


class IsBaremeTests(TestCase):
    def test_bareme_premiere_tranche_10pct(self):
        out = selectors.is_bareme(Decimal('200000'))
        self.assertEqual(out['is_bareme'], Decimal('20000.00'))
        self.assertEqual(len(out['tranches']), 1)
        self.assertEqual(out['tranches'][0]['taux'], Decimal('10'))

    def test_bareme_deuxieme_tranche_20pct(self):
        # 300 000 @10 % + 200 000 @20 % = 30 000 + 40 000 = 70 000.
        out = selectors.is_bareme(Decimal('500000'))
        self.assertEqual(out['is_bareme'], Decimal('70000.00'))
        self.assertEqual(len(out['tranches']), 2)

    def test_bareme_tranche_ouverte_31pct(self):
        # 300k@10 + 700k@20 + 500k@31 = 30 000 + 140 000 + 155 000 = 325 000.
        out = selectors.is_bareme(Decimal('1500000'))
        self.assertEqual(out['is_bareme'], Decimal('325000.00'))
        self.assertEqual(len(out['tranches']), 3)
        self.assertEqual(out['tranches'][2]['taux'], Decimal('31'))

    def test_resultat_negatif_is_nul(self):
        out = selectors.is_bareme(Decimal('-50000'))
        self.assertEqual(out['is_bareme'], Decimal('0.00'))
        self.assertEqual(out['tranches'], [])


class CotisationMinimaleTests(TestCase):
    def test_cm_calculee_au_dessus_du_minimum(self):
        # 0,25 % de 10 000 000 = 25 000 > plancher 3 000.
        out = selectors.cotisation_minimale(Decimal('10000000'))
        self.assertEqual(out['cm_calculee'], Decimal('25000.00'))
        self.assertEqual(out['cm'], Decimal('25000.00'))

    def test_cm_plancher_forfaitaire(self):
        # 0,25 % de 100 000 = 250 < plancher 3 000 → CM = 3 000.
        out = selectors.cotisation_minimale(Decimal('100000'))
        self.assertEqual(out['cm_calculee'], Decimal('250.00'))
        self.assertEqual(out['cm'], Decimal('3000.00'))

    def test_cm_base_nulle(self):
        out = selectors.cotisation_minimale(Decimal('0'))
        self.assertEqual(out['cm'], Decimal('3000.00'))


class EstimerIsTests(TestCase):
    def setUp(self):
        self.co = make_company('fg140', 'FG140 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = make_exercice(self.co)

    def test_estimation_depuis_cpc(self):
        # Produits 800 000, charges 300 000 → résultat 500 000.
        _resultat(self.co, '800000', '300000')
        out = selectors.estimer_is(self.co, self.exercice)
        self.assertEqual(out['resultat_comptable'], Decimal('500000.00'))
        self.assertEqual(out['resultat_fiscal'], Decimal('500000.00'))
        # IS barème sur 500 000 = 70 000 ; CM = 0,25 % de 800 000 = 2 000 < 3 000.
        self.assertEqual(out['bareme']['is_bareme'], Decimal('70000.00'))
        self.assertEqual(out['is_du'], Decimal('70000.00'))
        self.assertEqual(out['base_retenue'], 'bareme')

    def test_reintegrations_et_deductions(self):
        _resultat(self.co, '800000', '300000')
        out = selectors.estimer_is(
            self.co, self.exercice,
            reintegrations=Decimal('100000'), deductions=Decimal('50000'))
        # 500 000 + 100 000 − 50 000 = 550 000.
        self.assertEqual(out['resultat_fiscal'], Decimal('550000.00'))

    def test_cotisation_minimale_plancher_quand_perte(self):
        # Perte : charges > produits → IS barème nul, CM s'applique.
        _resultat(self.co, '100000', '300000')
        out = selectors.estimer_is(self.co, self.exercice)
        self.assertEqual(out['resultat_fiscal'], Decimal('-200000.00'))
        self.assertEqual(out['bareme']['is_bareme'], Decimal('0.00'))
        # CM = 0,25 % de 100 000 = 250 < 3 000 → 3 000.
        self.assertEqual(out['is_du'], Decimal('3000.00'))
        self.assertEqual(out['base_retenue'], 'cotisation_minimale')

    def test_exercice_autre_societe_refuse(self):
        autre = make_company('fg140-x', 'FG140 X')
        services.seed_plan_comptable(autre)
        with self.assertRaises(ValueError):
            selectors.estimer_is(autre, self.exercice)


class EcheancierAcomptesTests(TestCase):
    def setUp(self):
        self.co = make_company('fg140-ech', 'FG140 Ech')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = make_exercice(self.co)

    def test_quatre_acomptes_25pct(self):
        out = selectors.echeancier_acomptes(
            self.co, self.exercice, is_reference=Decimal('40000'))
        self.assertEqual(len(out['acomptes']), 4)
        for acompte in out['acomptes']:
            self.assertEqual(acompte['montant'], Decimal('10000.00'))
        self.assertEqual(out['total_acomptes'], Decimal('40000.00'))

    def test_echeances_aux_3_6_9_12_mois(self):
        out = selectors.echeancier_acomptes(
            self.co, self.exercice, is_reference=Decimal('40000'))
        echeances = [a['date_echeance'] for a in out['acomptes']]
        self.assertEqual(echeances, [
            date(2026, 3, 31), date(2026, 6, 30),
            date(2026, 9, 30), date(2026, 12, 31)])

    def test_arrondi_solde_sur_dernier_acompte(self):
        # 10 000 / 4 = 2 500 exactement ; testons un montant non divisible.
        out = selectors.echeancier_acomptes(
            self.co, self.exercice, is_reference=Decimal('10000.10'))
        total = sum(a['montant'] for a in out['acomptes'])
        self.assertEqual(total, Decimal('10000.10'))

    def test_reference_par_defaut_depuis_estimation(self):
        _resultat(self.co, '800000', '300000')
        out = selectors.echeancier_acomptes(self.co, self.exercice)
        # IS estimé = 70 000 → acompte unitaire 17 500.
        self.assertEqual(out['is_reference'], Decimal('70000.00'))
        self.assertEqual(out['acomptes'][0]['montant'], Decimal('17500.00'))


class RegularisationTests(TestCase):
    def setUp(self):
        self.co = make_company('fg140-reg', 'FG140 Reg')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = make_exercice(self.co)

    def test_regularisation_a_payer(self):
        _resultat(self.co, '800000', '300000')
        # IS dû = 70 000 ; acomptes basés sur un IS N-1 plus faible (40 000).
        out = selectors.regularisation_is(
            self.co, self.exercice, is_reference=Decimal('40000'))
        self.assertEqual(out['is_du'], Decimal('70000.00'))
        self.assertEqual(out['total_acomptes'], Decimal('40000.00'))
        self.assertEqual(out['regularisation'], Decimal('30000.00'))
        self.assertEqual(out['sens'], 'a_payer')
        self.assertEqual(out['date_limite_paiement'], date(2027, 3, 31))

    def test_regularisation_excedent(self):
        _resultat(self.co, '800000', '300000')
        out = selectors.regularisation_is(
            self.co, self.exercice, is_reference=Decimal('100000'))
        # IS dû 70 000 − acomptes 100 000 = −30 000 (excédent / crédit d'IS).
        self.assertEqual(out['regularisation'], Decimal('-30000.00'))
        self.assertEqual(out['sens'], 'excedent')

    def test_aide_synthese_complete(self):
        _resultat(self.co, '800000', '300000')
        out = selectors.aide_calcul_is(
            self.co, self.exercice, is_reference=Decimal('40000'))
        self.assertIn('estimation', out)
        self.assertIn('echeancier_acomptes', out)
        self.assertIn('regularisation', out)
        self.assertEqual(out['estimation']['is_du'], Decimal('70000.00'))
        self.assertEqual(
            out['regularisation']['regularisation'], Decimal('30000.00'))


class AideIsApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg140-a', 'FG140 A')
        self.co_b = make_company('fg140-b', 'FG140 B')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
            services.seed_journaux(co)
        self.ex_a = make_exercice(self.co_a)
        self.ex_b = make_exercice(self.co_b)
        _resultat(self.co_a, '800000', '300000')
        self.user_a = make_user(self.co_a, 'fg140-user-a')
        self.user_b = make_user(self.co_b, 'fg140-user-b')

    def test_isolation_par_societe(self):
        out_a = selectors.estimer_is(self.co_a, self.ex_a)
        out_b = selectors.estimer_is(self.co_b, self.ex_b)
        self.assertEqual(out_a['resultat_comptable'], Decimal('500000.00'))
        # B n'a aucune écriture → résultat nul → IS = cotisation minimale.
        self.assertEqual(out_b['resultat_comptable'], Decimal('0.00'))
        self.assertEqual(out_b['is_du'], Decimal('3000.00'))

    def test_endpoint_json(self):
        api = auth(self.user_a)
        resp = api.get(
            f'/api/django/compta/etats/aide-is/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Decimal(str(resp.data['estimation']['is_du'])), Decimal('70000.00'))
        self.assertEqual(len(resp.data['echeancier_acomptes']['acomptes']), 4)

    def test_endpoint_exercice_requis(self):
        resp = auth(self.user_a).get('/api/django/compta/etats/aide-is/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_exercice_introuvable(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/aide-is/?exercice=999999')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_isole_b_ne_voit_pas_exercice_a(self):
        # B ne peut pas viser l'exercice de A (scopé société → 404).
        resp = auth(self.user_b).get(
            f'/api/django/compta/etats/aide-is/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_export_csv(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/aide-is/?exercice={self.ex_a.pk}'
            '&export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('Aide au calcul de l', body)
        self.assertIn('IS d', body)
        self.assertIn('Acompte 1', body)

    def test_endpoint_reintegrations_param(self):
        resp = auth(self.user_a).get(
            f'/api/django/compta/etats/aide-is/?exercice={self.ex_a.pk}'
            '&reintegrations=100000&deductions=50000')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Decimal(str(resp.data['estimation']['resultat_fiscal'])),
            Decimal('550000.00'))

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg140-normal', role='normal')
        resp = auth(normal).get(
            f'/api/django/compta/etats/aide-is/?exercice={self.ex_a.pk}')
        self.assertEqual(resp.status_code, 403)
