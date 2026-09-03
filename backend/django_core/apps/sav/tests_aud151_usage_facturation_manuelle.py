"""AUD151 — Facturation d'usage (XCTR16) absente du bouton manuel « Facturer ».

`ContratMaintenanceViewSet.facturer` (sav/maintenance.py:290-342) invoquait
UNIQUEMENT `creer_facture_contrat` puis journalisait — il n'appelait JAMAIS
`calculer_ligne_usage_contrat`/`_ajouter_ligne_usage_contrat`, invoquées
seulement par le chemin beat `facturer_contrat_maintenance_beat`
(sav/services.py:397-433, appel conditionnel :427-428).

Rouge avant correctif : un contrat de maintenance à tarif d'usage facturé à la
main (rattrapage, beat en panne, facturation anticipée) partait au client sans
la ligne d'usage — le revenu variable de la période était perdu, définitivement
et en silence. Vert : les deux chemins passent par le même service et
produisent la MÊME facture, ligne d'usage comprise.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models_installation import Installation
from apps.monitoring.models import ProductionReading
from apps.sav import services as sav_services
from apps.sav.models import ContratMaintenance
from apps.ventes.models import Facture

User = get_user_model()
BASE_URL = '/api/django/sav/contrats-maintenance/'


class Aud151UsageFacturationManuelleTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud151', defaults={'nom': 'AUD151 Co'})
        self.user = User.objects.create_user(
            username='aud151_user', password='x', role_legacy='responsable',
            company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='AUD151', prenom='Client',
            email='aud151@example.invalid', telephone='+212600000151')
        self.inst = Installation.objects.create(
            company=self.co, reference='CHT-AUD151', client=self.cli)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _contrat(self, reference_debut=date(2024, 1, 1)):
        return ContratMaintenance.objects.create(
            company=self.co, client=self.cli, installation=self.inst,
            periodicite='annuel', date_debut=reference_debut, actif=True,
            prix=Decimal('3000'), facturation_active=True,
            tarif_usage=Decimal('1.5'),
            franchise_incluse=Decimal('100'),
            unite_usage=ContratMaintenance.UniteUsage.KWH)

    def _reading(self, contrat, kwh):
        """Relevé placé DANS la période de service de la facture à venir
        (``derniere_facturation``/``date_debut`` → + périodicité)."""
        ProductionReading.objects.create(
            company=self.co, installation=self.inst,
            date=contrat.date_debut, energy_kwh=kwh)

    def _lignes_usage(self, facture):
        return [
            ligne for ligne in facture.lignes.all()
            if "usage" in ligne.designation.lower()
        ]

    # ── le scénario du constat ──────────────────────────────────────────────

    def test_action_manuelle_contient_la_ligne_dusage(self):
        """ROUGE avant AUD151 : aucune ligne d'usage sur la facture manuelle."""
        contrat = self._contrat()
        self._reading(contrat, Decimal('300'))
        r = self.api.post(f'{BASE_URL}{contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['facture_id'])
        lignes_usage = self._lignes_usage(facture)
        self.assertEqual(len(lignes_usage), 1)
        # (300 - 100) * 1.5 = 300.00
        self.assertEqual(lignes_usage[0].prix_unitaire, Decimal('300.00'))

    def test_manuelle_et_beat_produisent_le_meme_montant_dusage(self):
        contrat_manuel = self._contrat()
        self._reading(contrat_manuel, Decimal('300'))
        r = self.api.post(f'{BASE_URL}{contrat_manuel.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        facture_manuelle = Facture.objects.get(pk=r.data['facture_id'])

        contrat_beat = self._contrat()
        facture_beat = sav_services.facturer_contrat_maintenance_beat(
            contrat_beat, user=self.user)

        usage_manuel = self._lignes_usage(facture_manuelle)[0].prix_unitaire
        usage_beat = self._lignes_usage(facture_beat)[0].prix_unitaire
        self.assertEqual(usage_manuel, usage_beat)
        self.assertEqual(
            facture_manuelle.montant_ttc, facture_beat.montant_ttc)

    def test_le_forfait_nest_jamais_ecrase_par_la_ligne_dusage(self):
        """La facture vaut forfait + usage — jamais l'usage seul (les totaux
        sont recalculés depuis les lignes, or le forfait n'en avait aucune)."""
        contrat = self._contrat()
        self._reading(contrat, Decimal('300'))
        r = self.api.post(f'{BASE_URL}{contrat.pk}/facturer/')
        facture = Facture.objects.get(pk=r.data['facture_id'])
        # Forfait 3 000 TTC = 2 500 HT ; usage 300 HT → 2 800 HT, 3 360 TTC.
        self.assertEqual(facture.montant_ht, Decimal('2800.00'))
        self.assertEqual(facture.montant_ttc, Decimal('3360.00'))
        self.assertEqual(facture.lignes.count(), 2)

    def test_contrat_sans_tarif_usage_inchange(self):
        contrat = self._contrat()
        contrat.tarif_usage = None
        contrat.save(update_fields=['tarif_usage'])
        r = self.api.post(f'{BASE_URL}{contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['facture_id'])
        self.assertEqual(facture.lignes.count(), 0)
        self.assertEqual(facture.montant_ttc, Decimal('3000'))

    def test_sans_releve_la_ligne_dusage_est_omise_sans_erreur(self):
        contrat = self._contrat()  # aucun ProductionReading
        r = self.api.post(f'{BASE_URL}{contrat.pk}/facturer/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['facture_id'])
        self.assertEqual(self._lignes_usage(facture), [])
        self.assertEqual(facture.montant_ttc, Decimal('3000'))
