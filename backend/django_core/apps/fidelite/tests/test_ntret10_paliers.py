"""NTRET10 — paliers de fidélité (Bronze/Argent/Or) + remise palier.

Le branchement de la remise à l'écran caisse (``apps.pos.services``) est HORS
PÉRIMÈTRE de cette lane (apps.pos appartient à une autre lane) : ce lot livre
le calcul de palier + le sélecteur `palier_et_remise_pour_client`, PRÊT à être
consommé par ``apps.pos`` (lecture seule, jamais un import de
``apps.fidelite.models``)."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.crm.models import Client
from apps.fidelite.models import CompteFidelite, PalierFidelite, ProgrammeFidelite
from apps.fidelite.selectors import palier_et_remise_pour_client
from apps.fidelite.services import crediter_points_pour_vente, recalculer_palier
from apps.records.models import Activity
from authentication.models import Company


def _company(nom='Société Paliers'):
    return Company.objects.create(nom=nom)


def _client(company, nom='Client Paliers'):
    return Client.objects.create(company=company, nom=nom)


class RecalculerPalierTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.client_crm = _client(self.company)
        self.programme = ProgrammeFidelite.objects.create(
            company=self.company, actif=True, points_par_mad=Decimal('1.00'))
        self.bronze = PalierFidelite.objects.create(
            company=self.company, programme=self.programme, libelle='Bronze',
            ordre=1, seuil_points=100, remise_pct=Decimal('2.00'))
        self.argent = PalierFidelite.objects.create(
            company=self.company, programme=self.programme, libelle='Argent',
            ordre=2, seuil_points=500, remise_pct=Decimal('5.00'))
        self.or_ = PalierFidelite.objects.create(
            company=self.company, programme=self.programme, libelle='Or',
            ordre=3, seuil_points=1000, remise_pct=Decimal('10.00'))

    def test_franchir_un_seuil_change_le_palier_automatiquement(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('150.00'), source_type='vente_comptoir')

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertEqual(compte.palier_actuel_id, self.bronze.id)

    def test_palier_progresse_avec_le_solde(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('150.00'), source_type='vente_comptoir')
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('600.00'), source_type='vente_comptoir')

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertEqual(compte.solde_points, 750)
        self.assertEqual(compte.palier_actuel_id, self.argent.id)

    def test_sous_le_premier_seuil_aucun_palier(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('10.00'), source_type='vente_comptoir')

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertIsNone(compte.palier_actuel_id)

    def test_ca_cumule_atteint_le_seuil_meme_sans_seuil_points(self):
        PalierFidelite.objects.filter(pk=self.or_.pk).delete()
        vip = PalierFidelite.objects.create(
            company=self.company, programme=self.programme, libelle='VIP CA',
            ordre=4, seuil_ca_cumule=Decimal('1000.00'))
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('1200.00'), source_type='facture')

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        self.assertEqual(compte.palier_actuel_id, vip.id)

    def test_historique_de_changement_de_palier_trace_au_chatter(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('150.00'), source_type='vente_comptoir')

        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)
        ct = ContentType.objects.get_for_model(CompteFidelite)
        entries = Activity.objects.filter(
            content_type=ct, object_id=compte.pk, field='palier_actuel')
        self.assertEqual(entries.count(), 1)
        entry = entries.first()
        self.assertEqual(entry.new_value, 'Bronze')

    def test_recalcul_idempotent_pas_de_double_trace(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('150.00'), source_type='vente_comptoir')
        compte = CompteFidelite.objects.get(
            company=self.company, client=self.client_crm)

        changed = recalculer_palier(compte)

        self.assertFalse(changed)
        ct = ContentType.objects.get_for_model(CompteFidelite)
        self.assertEqual(
            Activity.objects.filter(
                content_type=ct, object_id=compte.pk,
                field='palier_actuel').count(),
            1)

    def test_selecteur_palier_et_remise_pour_pos(self):
        crediter_points_pour_vente(
            company=self.company, client=self.client_crm,
            montant_ttc=Decimal('150.00'), source_type='vente_comptoir')

        info = palier_et_remise_pour_client(self.company, self.client_crm.id)
        self.assertEqual(info['palier'], 'Bronze')
        self.assertEqual(info['remise_pct'], Decimal('2.00'))

    def test_selecteur_sans_compte_ne_leve_jamais(self):
        info = palier_et_remise_pour_client(self.company, 999999)
        self.assertIsNone(info['palier'])
        self.assertIsNone(info['remise_pct'])

    def test_isolation_multi_tenant_paliers(self):
        autre_company = _company('Autre Société Paliers')
        autre_client = _client(autre_company, 'Autre Client')
        autre_programme = ProgrammeFidelite.objects.create(
            company=autre_company, actif=True, points_par_mad=Decimal('1.00'))
        PalierFidelite.objects.create(
            company=autre_company, programme=autre_programme, libelle='Bronze',
            ordre=1, seuil_points=50, remise_pct=Decimal('1.00'))

        crediter_points_pour_vente(
            company=autre_company, client=autre_client,
            montant_ttc=Decimal('80.00'), source_type='facture')

        # Le compte de la société A ne doit jamais voir le palier de B.
        self.assertFalse(
            CompteFidelite.objects.filter(
                company=self.company, client=self.client_crm,
                palier_actuel__isnull=False).exists())
        info = palier_et_remise_pour_client(self.company, self.client_crm.id)
        self.assertIsNone(info['palier'])
