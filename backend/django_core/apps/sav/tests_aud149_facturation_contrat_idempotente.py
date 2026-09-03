"""AUD149 — Facturation d'un contrat de maintenance : aucune garde avant
création — double facturation possible et invisible dans le journal.

`ContratMaintenanceViewSet.facturer` (sav/maintenance.py:288-343) appelait
directement `creer_facture_contrat` SANS vérifier `contrat.facturation_due()`
ni aucun état « déjà facturé cette période », et la SEULE garde anti-doublon
existante (`contrats.services.enregistrer_cycle`, qui lève `RejeuError` si un
cycle « genere » existe déjà pour (source_type, source_id, periode)) n'était
appelée qu'APRÈS coup, enveloppée dans un `except Exception: pass`. Même patron
côté beat quotidien.

Rouge avant correctif : deux clics sur « Facturer », ou un clic le jour du
passage du beat, produisaient DEUX factures d'abonnement pour le même mois sans
qu'aucune trace ne le signale. Vert : UNE facture et un 409 explicite.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.contrats.models import CycleFacturationLog
from apps.crm.models import Client
from apps.sav import services as sav_services
from apps.sav.models import ContratMaintenance
from apps.ventes.models import Facture

User = get_user_model()
BASE_URL = '/api/django/sav/contrats-maintenance/'


class Aud149FacturationContratIdempotenteTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud149', defaults={'nom': 'AUD149 Co'})
        self.user = User.objects.create_user(
            username='aud149_user', password='x', role_legacy='responsable',
            company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='AUD149', prenom='Client',
            email='aud149@example.invalid', telephone='+212600000149')
        self.contrat = ContratMaintenance.objects.create(
            company=self.co, client=self.cli, periodicite='annuel',
            date_debut=date(2024, 1, 1), actif=True, prix=Decimal('3000'),
            facturation_active=True, derniere_facturation=None)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _factures(self):
        return Facture.objects.filter(company=self.co)

    def _periode(self):
        return timezone.localdate().strftime('%Y-%m')

    # ── le scénario du constat ──────────────────────────────────────────────

    def test_double_clic_facturer_ne_produit_quune_facture(self):
        """ROUGE avant AUD149 : deux factures d'abonnement pour le même mois."""
        r1 = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r2.status_code, 409, r2.data)
        self.assertFalse(r2.data['ok'])
        self.assertEqual(self._factures().count(), 1)

    def test_action_manuelle_le_jour_du_beat_ne_produit_quune_facture(self):
        """ROUGE avant AUD149 : le beat puis le clic manuel facturaient 2×."""
        sav_services.facturer_contrat_maintenance_beat(
            self.contrat, user=self.user)
        self.assertEqual(self._factures().count(), 1)
        r = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(self._factures().count(), 1)

    def test_beat_apres_action_manuelle_ne_refacture_pas(self):
        r = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        self.contrat.refresh_from_db()
        with self.assertRaises(sav_services.FacturationContratDoublonError):
            sav_services.facturer_contrat_maintenance_beat(
                self.contrat, user=self.user)
        self.assertEqual(self._factures().count(), 1)

    def test_cycle_deja_genere_refuse_avant_toute_creation(self):
        """La garde de cycle passe AVANT la création, pas après : un cycle
        « genere » préexistant refuse la facturation SANS créer de facture."""
        from apps.contrats import services as contrats_services

        contrats_services.enregistrer_cycle(
            self.co,
            source_type=CycleFacturationLog.SourceType.SAV_MAINTENANCE,
            source_id=self.contrat.pk,
            periode=self._periode(),
            statut=CycleFacturationLog.Statut.GENERE,
        )
        with self.assertRaises(sav_services.FacturationContratDoublonError):
            sav_services.facturer_contrat_maintenance(
                self.contrat, user=self.user, company=self.co)
        self.assertEqual(self._factures().count(), 0)

    def test_succes_journalise_le_cycle_avec_sa_facture(self):
        r = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        cycles = CycleFacturationLog.objects.filter(
            company=self.co,
            source_type=CycleFacturationLog.SourceType.SAV_MAINTENANCE,
            source_id=self.contrat.pk,
            periode=self._periode())
        self.assertEqual(cycles.count(), 1)
        cycle = cycles.first()
        self.assertEqual(cycle.statut, CycleFacturationLog.Statut.GENERE)
        self.assertEqual(cycle.facture_id, r.data['facture_id'])

    def test_echec_metier_ne_reserve_aucune_periode(self):
        """Prix absent : 400, aucune facture, et la période reste facturable
        une fois le prix renseigné (la réservation est annulée avec la
        transaction)."""
        self.contrat.prix = None
        self.contrat.save(update_fields=['prix'])
        r = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(self._factures().count(), 0)

        self.contrat.prix = Decimal('3000')
        self.contrat.save(update_fields=['prix'])
        r2 = self.api.post(f'{BASE_URL}{self.contrat.pk}/facturer/')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertEqual(self._factures().count(), 1)
