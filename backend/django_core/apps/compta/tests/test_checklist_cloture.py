"""XACC10 — Checklist de clôture de période + écriture de solde TVA.

Couvre :

* la checklist affiche l'état réel de chaque étape depuis les données (ex.
  dotations postées, rapprochements soldés, caisses clôturées) ;
* le solde TVA poste une écriture équilibrée égale à la déclaration FG137 ;
* le verrouillage reste possible avec des étapes ouvertes (jamais de blocage
  dur) ;
* idempotence du solde TVA par période.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CompteTresorerie, EcritureComptable, Journal


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _ecriture(company, code_journal, lignes_par_numero, *, jour):
    types = {'VTE': Journal.Type.VENTE, 'ACH': Journal.Type.ACHAT,
             'OD': Journal.Type.OPERATIONS_DIVERSES}
    journal = services._journal(company, types[code_journal])
    lignes = []
    for numero, debit, credit in lignes_par_numero:
        lignes.append({
            'compte': services.get_compte(company, numero),
            'debit': Decimal(debit), 'credit': Decimal(credit),
        })
    return services.creer_ecriture(
        company, journal, jour, 'Test XACC10', lignes)


class ChecklistClotureTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc10', 'XACC10 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.periode = services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 1, 31), libelle='Janvier 2026')

    def test_checklist_toutes_etapes_presentes(self):
        res = selectors.checklist_cloture_periode(self.periode)
        codes = {e['code'] for e in res['etapes']}
        self.assertEqual(codes, {
            'dotations', 'fnp_fae', 'rapprochements', 'caisses',
            'ecarts_change', 'tva_soldee'})

    def test_dotations_non_applicable_hors_decembre(self):
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'dotations')
        self.assertEqual(etape['statut'], 'non_applicable')

    def test_ecarts_change_toujours_non_applicable(self):
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'ecarts_change')
        self.assertEqual(etape['statut'], 'non_applicable')

    def test_fnp_fae_a_faire_par_defaut(self):
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'fnp_fae')
        self.assertEqual(etape['statut'], 'a_faire')

    def test_fnp_fae_fait_apres_provision(self):
        services.generer_provisions_fnp(
            self.co, date_periode=date(2026, 1, 20),
            items=[{'source_id': 1, 'reference': 'REC-1',
                    'montant_ht': Decimal('500')}],
            date_extourne=date(2026, 2, 1))
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'fnp_fae')
        self.assertEqual(etape['statut'], 'fait')

    def test_rapprochements_non_applicable_sans_rapprochement(self):
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'rapprochements')
        self.assertEqual(etape['statut'], 'non_applicable')

    def test_rapprochements_fait_quand_solde(self):
        banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('0'),
            compte_comptable=services.get_compte(self.co, '5141'))
        rap = services.creer_rapprochement(
            self.co, banque, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 1, 31), solde_releve=Decimal('0'))
        services.cloturer_rapprochement(rap)
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'rapprochements')
        self.assertEqual(etape['statut'], 'fait')

    def test_verrouillage_possible_avec_etapes_ouvertes(self):
        res = selectors.checklist_cloture_periode(self.periode)
        self.assertFalse(res['toutes_faites'])  # fnp_fae/tva_soldee à faire.
        # Le verrouillage reste possible malgré des étapes ouvertes.
        periode = services.cloturer_periode(self.periode)
        self.assertTrue(periode.verrouillee)


class SolderTvaPeriodeTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc10-tva', 'XACC10 TVA Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.periode = services.creer_periode(
            self.co, date(2026, 1, 1), date(2026, 1, 31), libelle='Janvier 2026')
        # Vente 1000 HT + 200 TVA (4455 crédit 200).
        _ecriture(self.co, 'VTE', [
            ('3421', '1200', '0'), ('7121', '0', '1000'), ('4455', '0', '200'),
        ], jour=date(2026, 1, 10))
        # Achat 500 HT + 50 TVA récupérable (3455 débit 50).
        _ecriture(self.co, 'ACH', [
            ('6111', '500', '0'), ('3455', '50', '0'), ('4411', '0', '550'),
        ], jour=date(2026, 1, 12))

    def test_solde_tva_ecriture_equilibree_egale_declaration(self):
        calc = selectors.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        ecr = services.solder_tva_periode(self.periode)
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        due = ecr.lignes.get(compte__numero='44552')
        self.assertEqual(due.credit, calc['tva_a_declarer'])
        self.assertEqual(ecr.lignes.get(compte__numero='4455').debit,
                         calc['tva_collectee'])
        self.assertEqual(ecr.lignes.get(compte__numero='3455').credit,
                         calc['tva_deductible'])

    def test_solde_tva_idempotent_par_periode(self):
        a = services.solder_tva_periode(self.periode)
        b = services.solder_tva_periode(self.periode)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='solde_tva').count(), 1)

    def test_checklist_tva_soldee_fait_apres_solde(self):
        services.solder_tva_periode(self.periode)
        res = selectors.checklist_cloture_periode(self.periode)
        etape = next(e for e in res['etapes'] if e['code'] == 'tva_soldee')
        self.assertEqual(etape['statut'], 'fait')

    def test_credit_de_tva_ne_poste_rien(self):
        co2 = make_company('xacc10-credit', 'XACC10 Crédit Co')
        services.seed_plan_comptable(co2)
        services.seed_journaux(co2)
        periode2 = services.creer_periode(
            co2, date(2026, 1, 1), date(2026, 1, 31), libelle='Janvier 2026')
        # Déductible > collectée → crédit de TVA, rien à solder.
        _ecriture(co2, 'ACH', [
            ('6111', '1000', '0'), ('3455', '200', '0'), ('4411', '0', '1200'),
        ], jour=date(2026, 1, 12))
        res = services.solder_tva_periode(periode2)
        self.assertIsNone(res)
