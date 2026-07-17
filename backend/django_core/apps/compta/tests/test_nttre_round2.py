"""Tests NTTRE11/13/14/16/18/36/38/41 — trésorerie avancée (round 2)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CompteTresorerie, Effet, LignePrevisionnelTresorerie,
    PlanRelanceTresorerie, PouvoirBancaire)

User = get_user_model()


def _company(slug):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return co


class ScenarioEtRuptureTests(TestCase):
    def setUp(self):
        self.co = _company('nttre16')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_scenario_filtre_et_rupture(self):
        lundi = timezone.localdate() - timedelta(
            days=timezone.localdate().weekday())
        LignePrevisionnelTresorerie.objects.create(
            company=self.co, libelle='Encaissement', date_prevue=lundi + timedelta(days=1),
            montant=Decimal('500'),
            scenario=LignePrevisionnelTresorerie.Scenario.REALISTE)
        LignePrevisionnelTresorerie.objects.create(
            company=self.co, libelle='Gros décaissement',
            date_prevue=lundi + timedelta(days=1), montant=Decimal('-2000'),
            scenario=LignePrevisionnelTresorerie.Scenario.PESSIMISTE)
        realiste = selectors.previsionnel_tresorerie(self.co)
        pessimiste = selectors.previsionnel_tresorerie(
            self.co, scenario='pessimiste')
        # Réaliste : +500 (inchangé), pas de rupture.
        self.assertEqual(realiste['semaines'][0]['flux_net'], Decimal('500'))
        self.assertIsNone(realiste['date_rupture_estimee'])
        # Pessimiste : -2000, solde négatif → rupture datée (NTTRE18).
        self.assertEqual(pessimiste['semaines'][0]['flux_net'], Decimal('-2000'))
        self.assertIsNotNone(pessimiste['date_rupture_estimee'])


class MultiDeviseTests(TestCase):
    def test_conversion_mad_et_ligne_mad_inchangee(self):
        co = _company('nttre13')
        services.seed_plan_comptable(co)
        banque = CompteTresorerie.objects.create(
            company=co, type_compte=CompteTresorerie.Type.BANQUE, libelle='EUR',
            devise='EUR', compte_comptable=services.get_compte(co, '5141'))
        rap = services.creer_rapprochement(
            co, banque, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31),
            solde_releve=Decimal('0'))
        eur = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 5), libelle='EUR op',
            montant=Decimal('100'), devise='EUR', taux_change=Decimal('11'))
        self.assertEqual(eur.montant_mad, Decimal('1100.00'))
        self.assertEqual(eur.ecart_mad, Decimal('1100.00'))  # rien de pointé
        mad = services.ajouter_ligne_releve(
            rap, date_operation=date(2026, 1, 6), libelle='MAD op',
            montant=Decimal('250'))
        self.assertEqual(mad.montant_mad, Decimal('250'))
        self.assertEqual(mad.ecart_mad, mad.ecart)


class FichierVirementBancaireTests(TestCase):
    def test_format_largeur_fixe_avec_controle(self):
        co = _company('nttre14')
        services.seed_plan_comptable(co)
        services.seed_journaux(co)
        banque = CompteTresorerie.objects.create(
            company=co, type_compte=CompteTresorerie.Type.BANQUE, libelle='BMCE',
            compte_comptable=services.get_compte(co, '5141'))
        run = services.creer_payment_run(
            co, date_paiement=timezone.localdate(), mode_paiement='virement',
            compte_tresorerie=banque, reference='R1',
            lignes=[{'tiers_id': 1, 'montant': Decimal('1000'),
                     'reference': 'F1', 'beneficiaire': 'Fourn A',
                     'rib': '011780000012345678901234'}])
        data = services.fichier_virement_bancaire(run)
        lignes = data['texte'].strip().split('\n')
        self.assertEqual(len(lignes), 2)  # 1 détail + 1 contrôle
        self.assertTrue(lignes[0].startswith('VIR'))
        self.assertTrue(lignes[-1].startswith('TOT'))
        # Toutes les lignes détail à la même largeur.
        self.assertEqual(len(lignes[0]), len('VIR') + 24 + 15 + 30 + 16)
        self.assertEqual(data['total'], Decimal('1000.00'))


class PlanRelanceTests(TestCase):
    def test_palier_differe_par_segment(self):
        co = _company('nttre11')
        PlanRelanceTresorerie.objects.create(
            company=co, nom='Grands comptes', segment_client='grand_compte',
            paliers=[{'jours': 7, 'canal': 'whatsapp', 'libelle': 'WA doux'}])
        PlanRelanceTresorerie.objects.create(
            company=co, nom='Défaut', segment_client='',
            paliers=[{'jours': 7, 'canal': 'email', 'libelle': 'Email doux'}])
        _, palier_gc = services.plan_relance_applicable(
            co, segment='grand_compte', jours_retard=10)
        _, palier_pme = services.plan_relance_applicable(
            co, segment='pme', jours_retard=10)
        self.assertEqual(palier_gc['canal'], 'whatsapp')
        self.assertEqual(palier_pme['canal'], 'email')  # retombe sur le défaut


class ExportsEtChatterTests(TestCase):
    def setUp(self):
        self.co = _company('nttre-exp')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', compte_comptable=services.get_compte(self.co, '5141'))
        self.user = User.objects.create_user(
            username='nttre-exp-user', password='x', company=self.co,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_export_csv_pouvoirs(self):
        PouvoirBancaire.objects.create(
            company=self.co, compte_tresorerie=self.banque,
            titulaire_nom='Titulaire A', plafond_signature_seul=Decimal('100000'))
        resp = self.api.get(
            '/api/django/compta/pouvoirs-bancaires/?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('Titulaire A', resp.content.decode('utf-8'))

    def test_export_xlsx_effets(self):
        Effet.objects.create(
            company=self.co, sens=Effet.Sens.RECEVOIR,
            type_effet=Effet.TypeEffet.CHEQUE, montant=Decimal('500'),
            date_emission=timezone.localdate(),
            date_echeance=timezone.localdate())
        resp = self.api.get('/api/django/compta/effets/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])

    def test_approbation_genere_activity_chatter(self):
        from apps.records.models import Activity
        createur = User.objects.create_user(
            username='nttre-createur2', password='x', company=self.co,
            role_legacy='responsable')
        appro1 = User.objects.create_user(
            username='nttre-appro1b', password='x', company=self.co,
            role_legacy='responsable')
        run = services.creer_payment_run(
            self.co, date_paiement=timezone.localdate(),
            mode_paiement='virement', compte_tresorerie=self.banque,
            reference='RC', lignes=[
                {'tiers_id': 1, 'montant': Decimal('100'),
                 'beneficiaire': 'F', 'rib': '011780000012345678901234'}],
            user=createur)
        services.approuver_payment_run(run, appro1)
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(type(run))
        self.assertTrue(Activity.objects.filter(
            company=self.co, content_type=ct, object_id=run.id).exists())
