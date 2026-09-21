"""Tests NTCON19 — Checklist de réception de lot (avant paiement final).

Couvre : checklist PAR LOT distincte de la checklist chantier existante
(``installations.ChantierChecklistItem`` jamais touchée), guard bloquant à la
réception tant qu'une étape obligatoire reste à cocher, mode avertissement,
préservation des étapes déjà cochées à la redéfinition, et ``date_fin_reelle``
posée à la réception (ce qui FIGE la pénalité NTCON15).
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from apps.btp_chantier import services
from apps.btp_chantier.models import Lot, LotChecklistItem

from .helpers import auth, make_chantier, make_company, make_lot, make_user

LOTS = '/api/django/btp-chantier/lots/'


class ChecklistLotTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)
        self.lot = make_lot(self.co, self.chantier, nom='Gros-œuvre')
        self.api = auth(self.user)

    def url(self, suffixe):
        return f'{LOTS}{self.lot.id}/{suffixe}/'

    def test_checklist_par_defaut_et_etat(self):
        resp = self.api.post(self.url('checklist'), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(
            resp.data['total'], len(services.CHECKLIST_RECEPTION_DEFAUT))
        self.assertEqual(resp.data['faits'], 0)
        self.assertFalse(resp.data['complete'])
        # Multi-tenant : la société est posée CÔTÉ SERVEUR.
        self.assertTrue(all(
            item.company_id == self.co.id
            for item in LotChecklistItem.objects.all()))

    def test_checklist_personnalisee(self):
        resp = self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'essais', 'libelle': 'Essais réalisés'},
            {'cle': 'doe', 'libelle': 'DOE remis', 'obligatoire': False},
        ]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['total'], 2)
        self.assertEqual(
            [e['cle'] for e in resp.data['etapes']], ['essais', 'doe'])

    def test_cle_en_double_refusee(self):
        resp = self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'essais', 'libelle': 'A'},
            {'cle': 'essais', 'libelle': 'B'},
        ]}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('double', resp.data['detail'])

    def test_cocher_pose_auteur_et_horodatage(self):
        self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'essais', 'libelle': 'Essais réalisés'},
        ]}, format='json')
        resp = self.api.post(
            self.url('cocher'), {'cle': 'essais', 'fait': True},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        item = LotChecklistItem.objects.get(lot=self.lot, cle='essais')
        self.assertTrue(item.fait)
        self.assertEqual(item.fait_par_id, self.user.id)
        self.assertIsNotNone(item.fait_le)

    def test_cocher_une_cle_inconnue_refuse(self):
        resp = self.api.post(
            self.url('cocher'), {'cle': 'inexistante'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('inconnue', resp.data['detail'])

    def test_redefinir_preserve_les_etapes_cochees(self):
        self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'essais', 'libelle': 'Essais réalisés'},
        ]}, format='json')
        self.api.post(
            self.url('cocher'), {'cle': 'essais'}, format='json')
        self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'essais', 'libelle': 'Essais et mise en service'},
            {'cle': 'doe', 'libelle': 'DOE remis'},
        ]}, format='json')
        item = LotChecklistItem.objects.get(lot=self.lot, cle='essais')
        self.assertTrue(item.fait)
        self.assertEqual(item.libelle, 'Essais et mise en service')

    # ── Guard de réception ──────────────────────────────────────────────
    def test_reception_bloquee_tant_que_la_checklist_est_incomplete(self):
        self.api.post(self.url('checklist'), {}, format='json')
        resp = self.api.post(self.url('terminer'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Checklist de réception incomplète', resp.data['detail'])
        self.lot.refresh_from_db()
        self.assertNotEqual(self.lot.statut, Lot.Statut.TERMINE)

    def test_reception_possible_checklist_complete(self):
        self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'essais', 'libelle': 'Essais réalisés'},
        ]}, format='json')
        self.api.post(self.url('cocher'), {'cle': 'essais'}, format='json')
        resp = self.api.post(self.url('terminer'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, Lot.Statut.TERMINE)
        # date_fin_reelle FIGE le retard pris en compte par NTCON15.
        self.assertEqual(self.lot.date_fin_reelle, timezone.localdate())

    def test_etape_non_obligatoire_ne_bloque_pas(self):
        self.api.post(self.url('checklist'), {'etapes': [
            {'cle': 'doe', 'libelle': 'DOE remis', 'obligatoire': False},
        ]}, format='json')
        resp = self.api.post(self.url('terminer'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_lot_sans_checklist_se_receptionne(self):
        resp = self.api.post(self.url('terminer'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_patch_statut_termine_est_garde_aussi(self):
        self.api.post(self.url('checklist'), {}, format='json')
        resp = self.api.patch(
            f'{LOTS}{self.lot.id}/', {'statut': 'termine'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('statut', resp.data)
        self.lot.refresh_from_db()
        self.assertNotEqual(self.lot.statut, Lot.Statut.TERMINE)

    def test_mode_avertissement_laisse_receptionner(self):
        self.api.post(self.url('checklist'), {}, format='json')
        config = dict(services.CONFIG_BTP_DEFAUTS)
        config['guard_checklist_lot_bloquant'] = False
        with patch.object(services, 'config_btp', return_value=config):
            resp = self.api.post(self.url('terminer'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, Lot.Statut.TERMINE)

    def test_checklist_lot_distincte_de_la_checklist_chantier(self):
        """La checklist d'exécution du CHANTIER (installations) n'est jamais
        touchée par la checklist de réception d'un LOT."""
        from apps.installations.models_chantier import ChantierChecklistItem

        self.api.post(self.url('checklist'), {}, format='json')
        self.assertEqual(
            ChantierChecklistItem.objects.filter(
                installation=self.chantier).count(), 0)
        self.assertGreater(
            LotChecklistItem.objects.filter(lot=self.lot).count(), 0)

    def test_checklist_cross_tenant_refusee(self):
        autre = make_company()
        chantier_autre = make_chantier(autre)
        lot_autre = make_lot(autre, chantier_autre, nom='Lot étranger')
        resp = self.api.post(
            f'{LOTS}{lot_autre.id}/checklist/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
