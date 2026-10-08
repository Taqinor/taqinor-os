"""ACHT6 (C-ACHT-005) — les champs posés par le SERVEUR ne s'écrivent plus
par un PATCH générique : `annule`, `motif_annulation`, `bom`,
`bon_commande` (chantier) et `facture_id`, `rdv_confirme`,
`rdv_confirme_le`, `rdv_reschedule_count`, `arrivee_dans_fenetre`
(intervention). Seules les actions dédiées les écrivent.

Rejoue CCRE-5 (PATCH annule=true : 200, chantier annulé, réservations
actives, garde CHT2 contournée sur un clôturé) et CINT-14 (facture_id
999999, reschedule 7 acceptés).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_champs_serveur"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import (
    Installation, Intervention, StockReservation,
)
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
BASE = '/api/django/installations'


class ChampsServeurTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht6', defaults={'nom': 'Co ACHT6'})
        self.user = User.objects.create_user(
            username='resp-acht6', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT6', sku='PAN-ACHT6',
            prix_vente=Decimal('100'), quantite_stock=50)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht6@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT6-1',
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'))
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')
        self.inst = Installation.objects.get(devis=devis)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user,
            statut=Intervention.Statut.TERMINEE)

    def _patch_chantier(self, inst, data):
        return self.api.patch(f'{BASE}/chantiers/{inst.id}/', data,
                              format='json')

    def _resas_actives(self):
        return StockReservation.objects.filter(
            installation=self.inst, active=True).count()

    def test_patch_annule_ignore(self):
        bom_avant = list(self.inst.bom)
        r = self._patch_chantier(self.inst, {
            'annule': True, 'motif_annulation': 'x',
            'bom': [], 'bon_commande': None})
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertFalse(self.inst.annule)
        self.assertIsNone(self.inst.motif_annulation)
        self.assertEqual(self.inst.bom, bom_avant)
        self.assertEqual(self._resas_actives(), 1)

    def test_patch_annule_cloture_ignore(self):
        cloture = Installation.objects.create(
            company=self.company, reference='CHT-ACHT6-CLOS',
            client=self.client_obj, statut=Installation.Statut.CLOTURE,
            cloture_verrouillee=True)
        r = self._patch_chantier(cloture, {'annule': True,
                                           'motif_annulation': 'x'})
        self.assertIn(r.status_code, (200, 400), r.data)
        cloture.refresh_from_db()
        # Garde CHT2 (motif + Directeur) non contournable par le PATCH.
        self.assertFalse(cloture.annule)

    def test_patch_reactiver_ignore(self):
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/',
                          {'motif': 'test'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self._patch_chantier(self.inst, {'annule': False})
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertTrue(self.inst.annule)
        self.assertEqual(self._resas_actives(), 0)

    def test_patch_facture_id_ignore(self):
        r = self.api.patch(f'{BASE}/interventions/{self.interv.id}/', {
            'facture_id': 999999, 'rdv_confirme': True,
            'rdv_confirme_le': '2026-10-08T10:00:00Z',
            'rdv_reschedule_count': 7, 'arrivee_dans_fenetre': True,
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.interv.refresh_from_db()
        self.assertIsNone(self.interv.facture_id)
        self.assertFalse(self.interv.rdv_confirme)
        self.assertIsNone(self.interv.rdv_confirme_le)
        self.assertEqual(self.interv.rdv_reschedule_count, 0)
        self.assertIsNone(self.interv.arrivee_dans_fenetre)

    def test_actions_ecrivent_toujours(self):
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/annuler/',
                          {'motif': 'Client se désiste'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertTrue(self.inst.annule)
        self.assertEqual(self.inst.motif_annulation, 'Client se désiste')
        r = self.api.post(f'{BASE}/chantiers/{self.inst.id}/reactiver/', {},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertFalse(self.inst.annule)
        self.assertEqual(self._resas_actives(), 1)
