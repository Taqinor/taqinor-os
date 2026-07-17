"""Tests NTFIN1-12 — Consolidation multi-sociétés (grand groupe).

Couvre le moniteur de consolidation complet : cycle daté + verrouillage
(NTFIN1), collecte idempotente des balances d'entités (NTFIN2), contrôles de
collecte (NTFIN3), mapping compte local → groupe (NTFIN4), conversion de devise
+ écart de conversion (NTFIN5), matching interco (NTFIN6), éliminations
réciproques (NTFIN7), marge interne sur stock (NTFIN8), titres + goodwill
(NTFIN9), intérêts minoritaires (NTFIN10), bilan/CPC consolidés (NTFIN11),
moniteur de consolidation (NTFIN12).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CycleConsolidation, EcritureElimination, EliminationTitres,
    EntiteConsolidation, Journal, LiasseRemontee, MappingConsolidation,
    MargeInterneStock, OperationInterco,
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


def _poster(company, d, libelle, lignes):
    services.seed_plan_comptable(company)
    services.seed_journaux(company)
    journal = services._journal(company, Journal.Type.OPERATIONS_DIVERSES)
    services.creer_ecriture(company, journal, d, libelle, [
        {'compte': services.get_compte(company, num), 'debit': Decimal(deb),
         'credit': Decimal(cre)} for num, deb, cre in lignes],
        statut='validee')


def _balance_simple(company, produit, charge):
    """Pose un CA (+ un achat si charge > 0) validés (grand livre équilibré)."""
    _poster(company, date(2026, 1, 10), 'CA', [
        ('3421', produit, '0'), ('7121', '0', produit)])
    if Decimal(charge) > 0:
        _poster(company, date(2026, 1, 11), 'Achat', [
            ('6111', charge, '0'), ('5141', '0', charge)])


def _cycle(company, **kw):
    from apps.compta.models import ExerciceComptable
    ex, _ = ExerciceComptable.objects.get_or_create(
        company=company, date_debut=date(2026, 1, 1),
        date_fin=date(2026, 12, 31), defaults={'libelle': '2026'})
    defaults = dict(
        company=company, libelle=kw.pop('libelle', 'Consol 2026'),
        exercice=ex, date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31),
        devise_presentation='MAD')
    defaults.update(kw)
    return CycleConsolidation.objects.create(**defaults)


class CycleConsolidationTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin-tete', 'Groupe SA')
        self.user = make_user(self.tete, 'ntfin-user')
        _balance_simple(self.tete, '100000', '60000')

    def test_ntfin1_verrouillage_refuse_modification(self):
        cycle = _cycle(self.tete, verrouille=True)
        with self.assertRaises(ValidationError):
            services.collecter_cycle(cycle)

    def test_ntfin1_api_ouvrir_verrouiller(self):
        cycle = _cycle(self.tete)
        resp = auth(self.user).post(
            f'/api/django/compta/cycles-consolidation/{cycle.id}/verrouiller/')
        self.assertEqual(resp.status_code, 200)
        cycle.refresh_from_db()
        self.assertTrue(cycle.verrouille)
        resp2 = auth(self.user).post(
            f'/api/django/compta/cycles-consolidation/{cycle.id}/ouvrir/')
        self.assertEqual(resp2.status_code, 200)
        cycle.refresh_from_db()
        self.assertFalse(cycle.verrouille)

    def test_ntfin2_collecte_idempotente(self):
        cycle = _cycle(self.tete)
        services.collecter_balance_entite(cycle, self.tete)
        services.collecter_balance_entite(cycle, self.tete)
        self.assertEqual(
            LiasseRemontee.objects.filter(cycle=cycle, entite=self.tete)
            .count(), 1)

    def test_ntfin3_balance_desequilibree_bloquant(self):
        cycle = _cycle(self.tete)
        LiasseRemontee.objects.create(
            company=self.tete, cycle=cycle, entite=self.tete,
            statut=LiasseRemontee.Statut.COLLECTE, devise_locale='MAD',
            snapshot_balance=[
                {'numero': '3421', 'classe': 3, 'debit': '100', 'credit': '0'},
                {'numero': '7121', 'classe': 7, 'debit': '0', 'credit': '80'},
            ])
        res = selectors.controles_collecte(cycle)
        self.assertTrue(res['bloquant'])
        self.assertTrue(any(a['type'] == 'balance_desequilibree'
                            for a in res['anomalies']))


class MappingConversionTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin-map-tete', 'Groupe SA')
        services.seed_plan_comptable(self.tete)

    def test_ntfin4_mapping_prefixe_le_plus_long(self):
        cg = services.get_compte(self.tete, '7121')
        MappingConsolidation.objects.create(
            company=self.tete, plan_local_prefixe='7', compte_groupe=cg)
        cg2 = services.get_compte(self.tete, '6111')
        MappingConsolidation.objects.create(
            company=self.tete, plan_local_prefixe='712', compte_groupe=cg2)
        # '7121' matche '7' et '712' → le plus long ('712') gagne.
        mapped = services.mapper_compte_groupe(self.tete, '7121')
        self.assertEqual(mapped.id, cg2.id)

    def test_ntfin5_conversion_eur_mad_ecart(self):
        cycle = _cycle(self.tete)
        liasse = LiasseRemontee.objects.create(
            company=self.tete, cycle=cycle, entite=self.tete,
            statut=LiasseRemontee.Statut.COLLECTE, devise_locale='EUR',
            snapshot_balance=[
                {'numero': '2340', 'classe': 2, 'debit': '1000', 'credit': '0'},
                {'numero': '1111', 'classe': 1, 'debit': '0', 'credit': '700'},
                {'numero': '7121', 'classe': 7, 'debit': '0', 'credit': '300'},
            ])
        res = services.convertir_entite(liasse, Decimal('10'), Decimal('11'))
        # Bilan au cours de clôture (×10), résultat au cours moyen (×11) :
        # débit 10000, crédit 7000+3300=10300 → CTA = +300.
        self.assertEqual(res['total_debit'], Decimal('10000.00'))
        self.assertEqual(res['total_credit'], Decimal('10300.00'))
        self.assertEqual(res['ecart_conversion'], Decimal('300.00'))
        self.assertTrue(res['equilibre'])


class IntercoTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin-ic-tete', 'Groupe SA')
        self.fille = make_company('ntfin-ic-fille', 'Fille SARL')
        self.cycle = _cycle(self.tete)

    def test_ntfin6_apparie_et_ecart(self):
        self.cycle.tolerance_interco = Decimal('1')
        self.cycle.save()
        egal = OperationInterco.objects.create(
            company=self.tete, cycle=self.cycle, entite_debit=self.tete,
            entite_credit=self.fille, compte_reciproque='3488',
            montant_declare_a=Decimal('5000'), montant_declare_b=Decimal('5000'))
        divergent = OperationInterco.objects.create(
            company=self.tete, cycle=self.cycle, entite_debit=self.tete,
            entite_credit=self.fille, compte_reciproque='4488',
            montant_declare_a=Decimal('5000'), montant_declare_b=Decimal('4000'))
        services.apparier_intercos(self.cycle)
        egal.refresh_from_db()
        divergent.refresh_from_db()
        self.assertEqual(egal.statut, OperationInterco.Statut.APPARIE)
        self.assertEqual(divergent.statut, OperationInterco.Statut.ECART)

    def test_ntfin7_elimination_annule_les_soldes(self):
        op = OperationInterco.objects.create(
            company=self.tete, cycle=self.cycle, entite_debit=self.tete,
            entite_credit=self.fille, compte_reciproque='3488',
            montant_declare_a=Decimal('5000'), montant_declare_b=Decimal('5000'))
        services.apparier_intercos(self.cycle)
        elims = services.generer_eliminations_reciproques(self.cycle)
        self.assertEqual(len(elims), 1)
        elim = elims[0]
        self.assertEqual(elim.total_debit, Decimal('5000'))
        self.assertEqual(elim.total_credit, Decimal('5000'))
        # Idempotent : ne redouble pas l'élimination d'un interco déjà éliminé.
        services.generer_eliminations_reciproques(self.cycle)
        self.assertEqual(
            EcritureElimination.objects.filter(source_interco=op).count(), 1)


class EliminationsAvanceesTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin-el-tete', 'Groupe SA')
        self.fille = make_company('ntfin-el-fille', 'Fille SARL')
        self.cycle = _cycle(self.tete)

    def test_ntfin8_marge_interne_avec_impot_differe(self):
        marge = MargeInterneStock.objects.create(
            company=self.tete, cycle=self.cycle, entite_vendeuse=self.tete,
            entite_acheteuse=self.fille, montant_stock=Decimal('10000'),
            taux_marge=Decimal('20'), taux_impot=Decimal('30'))
        elim = services.eliminer_marge_interne(marge)
        # Marge non réalisée = 10000 × 20 % = 2000 ; impôt différé 2000×30 %=600.
        self.assertEqual(marge.marge_non_realisee, Decimal('2000.00'))
        self.assertEqual(elim.total_debit, elim.total_credit)
        marge.refresh_from_db()
        self.assertEqual(marge.elimination_id, elim.id)

    def test_ntfin9_goodwill(self):
        et = EliminationTitres.objects.create(
            company=self.tete, cycle=self.cycle, entite_fille=self.fille,
            valeur_titres=Decimal('1000000'),
            quote_part_capitaux_propres=Decimal('800000'))
        elim = services.eliminer_titres(et)
        et.refresh_from_db()
        self.assertEqual(et.ecart_acquisition, Decimal('200000'))
        self.assertEqual(elim.total_debit, elim.total_credit)
        self.assertEqual(elim.type_elimination,
                         EcritureElimination.Type.TITRES)

    def test_ntfin10_interets_minoritaires(self):
        # Fille détenue à 80 %, résultat 100000 → 20000 aux minoritaires.
        _balance_simple(self.fille, '100000', '0')  # résultat 100000
        EntiteConsolidation.objects.create(
            company=self.tete, entite=self.fille, cycle=self.cycle,
            pourcentage_interet=Decimal('80'),
            methode=EntiteConsolidation.Methode.INTEGRATION_GLOBALE)
        services.collecter_cycle(self.cycle)
        elims = services.calculer_interets_minoritaires(self.cycle)
        self.assertEqual(len(elims), 1)
        elim = elims[0]
        self.assertEqual(elim.type_elimination,
                         EcritureElimination.Type.MINORITAIRES)
        # Part minoritaire du résultat = 100000 × 20 % = 20000.
        credit_minoritaires = sum(
            Decimal(str(li['credit'])) for li in elim.lignes)
        self.assertEqual(credit_minoritaires, Decimal('20000.00'))


class EtatsConsolidesTests(TestCase):
    def setUp(self):
        self.tete = make_company('ntfin-et-tete', 'Groupe SA')
        self.fille = make_company('ntfin-et-fille', 'Fille SARL')
        _balance_simple(self.tete, '100000', '60000')
        _balance_simple(self.fille, '50000', '20000')
        self.cycle = _cycle(self.tete)
        EntiteConsolidation.objects.create(
            company=self.tete, entite=self.fille, cycle=self.cycle,
            pourcentage_interet=Decimal('100'))

    def test_ntfin11_bilan_consolide_equilibre(self):
        services.collecter_cycle(self.cycle)
        bilan = selectors.bilan_consolide(self.cycle)
        self.assertTrue(bilan['equilibre'])
        cpc = selectors.cpc_consolide_v2(self.cycle)
        # Résultat = (100k-60k) tête + (50k-20k) fille = 70k.
        self.assertEqual(cpc['resultat'], Decimal('70000'))

    def test_ntfin12_moniteur_bloque_publication(self):
        # Balance déséquilibrée collectée → anomalie bloquante amont.
        LiasseRemontee.objects.create(
            company=self.tete, cycle=self.cycle, entite=self.tete,
            statut=LiasseRemontee.Statut.COLLECTE, devise_locale='MAD',
            snapshot_balance=[
                {'numero': '3421', 'classe': 3, 'debit': '100', 'credit': '0'},
            ])
        mon = selectors.moniteur_consolidation(self.cycle)
        self.assertFalse(mon['publication_possible'])
        self.assertGreater(mon['total_anomalies_bloquantes'], 0)

    def test_ntfin11_api_etats_consolides(self):
        services.collecter_cycle(self.cycle)
        user = make_user(self.tete, 'ntfin-et-user')
        resp = auth(user).get(
            f'/api/django/compta/cycles-consolidation/{self.cycle.id}'
            '/etats-consolides/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('bilan', resp.data)
        self.assertIn('cpc', resp.data)
