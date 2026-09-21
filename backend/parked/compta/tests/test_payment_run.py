"""Tests FG133/FG134 — campagnes de règlement fournisseurs (payment run) +
génération du fichier de virement bancaire.

Couvre :
* FG133 — création d'une campagne + lignes (company posée côté serveur, total
  recalculé), refus du montant non positif, gel (brouillon → proposée), post EN
  LOT (une écriture équilibrée : débit 4411 par ligne / crédit 5141 banque,
  dettes fournisseur soldées), idempotence, respect du verrou de période,
  isolation multi-société, suppression interdite une fois postée ;
* FG134 — fichier de virement (un virement par ligne, total, refus si non
  virement ou coordonnées bancaires manquantes), export CSV via l'endpoint ;
* endpoints API + gate de rôle (Admin/Responsable uniquement).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    CompteTresorerie, EcritureComptable, LigneEcriture, PaymentRun,
    PeriodeComptable,
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


class _RunSetup(TestCase):
    def setUp(self):
        self.co = make_company('fg133', 'FG133 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE',
            compte_comptable=services.get_compte(self.co, '5141'))
        self.caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse',
            compte_comptable=services.get_compte(self.co, '5161'))
        self.today = timezone.localdate()

    def _run(self, *, lignes=None, compte=None, mode='virement'):
        return services.creer_payment_run(
            self.co, date_paiement=self.today,
            mode_paiement=mode, compte_tresorerie=compte or self.banque,
            reference='RUN-1',
            lignes=lignes or [
                {'tiers_id': 1, 'montant': Decimal('1000'),
                 'reference': 'F001', 'beneficiaire': 'Fournisseur A',
                 'rib': '011780000012345678901234'},
                {'tiers_id': 2, 'montant': Decimal('500'),
                 'reference': 'F002', 'beneficiaire': 'Fournisseur B',
                 'iban': 'MA64011519000001205000534921'},
            ])


class PaymentRunServiceTests(_RunSetup):
    def test_creation_pose_company_et_total(self):
        run = self._run()
        self.assertEqual(run.company_id, self.co.id)
        self.assertEqual(run.statut, PaymentRun.Statut.BROUILLON)
        self.assertEqual(run.lignes.count(), 2)
        self.assertEqual(run.total, Decimal('1500'))
        for ligne in run.lignes.all():
            self.assertEqual(ligne.company_id, self.co.id)

    def test_montant_non_positif_refuse(self):
        with self.assertRaises(ValidationError):
            self._run(lignes=[{'tiers_id': 1, 'montant': Decimal('0')}])

    def test_figer_passe_en_proposee(self):
        run = self._run()
        run = services.figer_payment_run(run)
        self.assertEqual(run.statut, PaymentRun.Statut.PROPOSEE)

    def test_figer_vide_refuse(self):
        run = services.creer_payment_run(
            self.co, date_paiement=self.today, compte_tresorerie=self.banque,
            lignes=[])
        with self.assertRaises(ValidationError):
            services.figer_payment_run(run)

    def test_poster_ecriture_equilibree(self):
        run = self._run()
        ecriture = services.poster_payment_run(run)
        run.refresh_from_db()
        self.assertEqual(run.statut, PaymentRun.Statut.POSTEE)
        self.assertTrue(run.posted)
        self.assertEqual(ecriture.statut, EcritureComptable.Statut.VALIDEE)
        self.assertTrue(ecriture.est_equilibree)
        # Une ligne débit 4411 par ligne + un crédit banque.
        lignes = list(ecriture.lignes.all())
        self.assertEqual(len(lignes), 3)
        debit_4411 = sum(
            (lig.debit for lig in lignes if lig.compte.numero == '4411'),
            Decimal('0'))
        self.assertEqual(debit_4411, Decimal('1500'))
        credit_banque = sum(
            (lig.credit for lig in lignes if lig.compte.numero == '5141'),
            Decimal('0'))
        self.assertEqual(credit_banque, Decimal('1500'))
        # L'auxiliaire tiers est reporté sur les lignes fournisseur.
        tiers = {lig.tiers_id for lig in lignes if lig.tiers_id is not None}
        self.assertEqual(tiers, {1, 2})

    def test_poster_idempotent(self):
        run = self._run()
        e1 = services.poster_payment_run(run)
        e2 = services.poster_payment_run(run)
        self.assertEqual(e1.id, e2.id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                company=self.co, source_type='payment_run').count(), 1)

    def test_poster_sans_compte_refuse(self):
        run = services.creer_payment_run(
            self.co, date_paiement=self.today, compte_tresorerie=None,
            lignes=[{'tiers_id': 1, 'montant': Decimal('100'), 'rib': 'X'}])
        with self.assertRaises(ValidationError):
            services.poster_payment_run(run)

    def test_poster_periode_close_refuse(self):
        run = self._run()
        PeriodeComptable.objects.create(
            company=self.co,
            date_debut=self.today - timedelta(days=15),
            date_fin=self.today + timedelta(days=15),
            verrouillee=True)
        with self.assertRaises(ValidationError):
            services.poster_payment_run(run)

    def test_ajout_ligne_apres_post_refuse(self):
        run = self._run()
        services.poster_payment_run(run)
        run.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.ajouter_ligne_payment_run(
                run, tiers_id=3, montant=Decimal('100'))

    def test_isolation_multi_societe(self):
        other = make_company('fg133-other', 'Autre')
        services.seed_plan_comptable(other)
        services.seed_journaux(other)
        run = self._run()
        services.poster_payment_run(run)
        self.assertEqual(
            LigneEcriture.objects.filter(company=other).count(), 0)


class FichierVirementTests(_RunSetup):
    def test_fichier_virement_lignes_et_total(self):
        run = self._run()
        data = services.fichier_virement(run)
        self.assertEqual(data['nb_lignes'], 2)
        self.assertEqual(data['total'], Decimal('1500.00'))
        self.assertEqual(data['headers'][0], 'Beneficiaire')
        # Bénéficiaire + RIB/IBAN présents sur chaque ligne.
        self.assertEqual(data['rows'][0][0], 'Fournisseur A')
        self.assertEqual(data['rows'][0][1], '011780000012345678901234')

    def test_fichier_virement_non_virement_refuse(self):
        run = self._run(mode='cheque')
        with self.assertRaises(ValidationError):
            services.fichier_virement(run)

    def test_fichier_virement_coordonnees_manquantes_refuse(self):
        run = services.creer_payment_run(
            self.co, date_paiement=self.today, compte_tresorerie=self.banque,
            mode_paiement='virement',
            lignes=[{'tiers_id': 9, 'montant': Decimal('200'),
                     'beneficiaire': 'Sans RIB'}])
        with self.assertRaises(ValidationError):
            services.fichier_virement(run)


class PaymentRunApiTests(_RunSetup):
    def test_create_via_api_pose_company(self):
        user = make_user(self.co, 'resp-fg133')
        api = auth(user)
        payload = {
            'reference': 'API-RUN',
            'mode_paiement': 'virement',
            'compte_tresorerie': self.banque.id,
            'date_paiement': self.today.isoformat(),
            'lignes': [
                {'tiers_id': 1, 'montant': '800', 'reference': 'F1',
                 'beneficiaire': 'Four A', 'rib': 'R1'},
            ],
        }
        resp = api.post(
            '/api/django/compta/payment-runs/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        run = PaymentRun.objects.get(id=resp.data['id'])
        self.assertEqual(run.company_id, self.co.id)
        self.assertEqual(run.lignes.count(), 1)
        self.assertEqual(Decimal(str(resp.data['total'])), Decimal('800'))

    def test_company_from_body_ignored(self):
        other = make_company('fg133-evil', 'Evil')
        user = make_user(self.co, 'resp2-fg133')
        api = auth(user)
        payload = {
            'company': other.id,  # tentative d'injection — doit être ignorée.
            'compte_tresorerie': self.banque.id,
            'date_paiement': self.today.isoformat(),
            'lignes': [{'tiers_id': 1, 'montant': '100', 'rib': 'R'}],
        }
        resp = api.post(
            '/api/django/compta/payment-runs/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        run = PaymentRun.objects.get(id=resp.data['id'])
        self.assertEqual(run.company_id, self.co.id)

    def test_poster_endpoint(self):
        run = self._run()
        user = make_user(self.co, 'resp3-fg133')
        api = auth(user)
        resp = api.post(
            f'/api/django/compta/payment-runs/{run.id}/poster/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'postee')

    def test_fichier_virement_endpoint_csv(self):
        run = self._run()
        user = make_user(self.co, 'resp4-fg133')
        api = auth(user)
        resp = api.get(
            f'/api/django/compta/payment-runs/{run.id}/fichier-virement/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        body = resp.content.decode('utf-8')
        self.assertIn('Beneficiaire', body)
        self.assertIn('Fournisseur A', body)

    def test_delete_postee_refuse(self):
        run = self._run()
        services.poster_payment_run(run)
        user = make_user(self.co, 'resp5-fg133')
        api = auth(user)
        resp = api.delete(
            f'/api/django/compta/payment-runs/{run.id}/')
        self.assertEqual(resp.status_code, 400)

    def test_role_gate_refuse_commercial(self):
        user = make_user(self.co, 'comm-fg133', role='commercial')
        api = auth(user)
        resp = api.get('/api/django/compta/payment-runs/')
        self.assertEqual(resp.status_code, 403)
