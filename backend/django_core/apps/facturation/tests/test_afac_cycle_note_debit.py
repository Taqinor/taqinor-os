"""AFAC32 (C-AFAC-026, D-AFAC-C4 option a) — cycle de vie complet de la note
de débit : création PARTIELLE seulement (lignes ou montant saisis — plus de
copie silencieuse de toute la facture), annulation d'une ND émise par un AVOIR
de note de débit (idempotente, tracée, reste dû revenu, statut recalculé), et
annulation de facture qui refuse une ND encore active.

Rejoue la sonde FCOR-3 (`{motif}` → ND 12000.00 copiée, `montant_du` doublé ;
`/notes-debit/<id>/annuler/` → 404 ; facture annulée, ND toujours émise).
Endpoints et services réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_cycle_note_debit"
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'note_debit_creation.json')


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class CycleNoteDebitTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC32 Co', slug=f'afac32-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac32_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cycle', prenom='AFAC32',
            email=f'afac32-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC32-{_nxt():04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('10000'),
            montant_tva=Decimal('2000'), montant_ttc=Decimal('12000'))

    def _creer_nd(self, corps):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            corps, format='json')

    def _du(self):
        from apps.ventes.models import Facture
        return Facture.objects.get(pk=self.facture.pk).montant_du

    def test_nd_sans_lignes_ni_montant_400(self):
        from apps.ventes.models import NoteDebit
        r = self._creer_nd({'motif': 'pénalité'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(
            r.data['detail'],
            'Saisissez les lignes ou le montant de la note de débit.')
        self.assertFalse(
            NoteDebit.objects.filter(facture=self.facture).exists())
        self.assertEqual(self._du(), Decimal('12000.00'))

    def test_nd_montant_saisi(self):
        from apps.ventes.models import NoteDebit
        r = self._creer_nd({'motif': 'pénalité', 'montant': '500.00',
                            'taux_tva': '20'})
        self.assertEqual(r.status_code, 201, r.data)
        nd = NoteDebit.objects.get(pk=r.data['id'])
        self.assertEqual(nd.total_ht, Decimal('500.00'))
        self.assertEqual(nd.total_ttc, Decimal('600.00'))
        self.assertEqual(self._du(), Decimal('12600.00'))
        # Contrat partagé (AFAC20) : la réponse porte les clés de l'exemple.
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.assertTrue(set(contrat['exemple']).issubset(set(r.data)))
        self.assertEqual(r.data['total_ttc'], '600.00')

    def test_annuler_nd(self):
        from apps.ventes.models import Avoir, FactureActivity
        r = self._creer_nd({'motif': 'pénalité', 'montant': '500.00',
                            'taux_tva': '20'})
        self.assertEqual(r.status_code, 201, r.data)
        nd_id = r.data['id']
        self.assertEqual(self._du(), Decimal('12600.00'))
        url = f'/api/django/ventes/notes-debit/{nd_id}/annuler/'
        r1 = self.api.post(url, {}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertTrue(r1.data['cree'])
        # CLAUSE PERSISTANCE : reste dû revenu, avoir de ND relu.
        self.assertEqual(self._du(), Decimal('12000.00'))
        avoir = Avoir.objects.get(note_debit_id=nd_id)
        self.assertEqual(avoir.total_ttc, Decimal('600.00'))
        self.assertTrue(FactureActivity.objects.filter(
            facture=self.facture, field='note_debit').exists())
        # Rejeu : aucun effet (même avoir, rien créé).
        r2 = self.api.post(url, {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertFalse(r2.data['cree'])
        self.assertEqual(r2.data['avoir']['id'], avoir.id)
        self.assertEqual(
            Avoir.objects.filter(note_debit_id=nd_id).count(), 1)
        self.assertEqual(self._du(), Decimal('12000.00'))

    def test_annuler_facture_avec_nd_active(self):
        from apps.ventes.models import Facture, NoteDebit
        r = self._creer_nd({'motif': 'pénalité', 'montant': '500.00',
                            'taux_tva': '20'})
        nd_id = r.data['id']
        refus = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/annuler/', {},
            format='json')
        self.assertEqual(refus.status_code, 400, refus.data)
        self.assertEqual(refus.data['code'], 'note_debit_active')
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.EMISE)
        # La ND annulée par avoir, la facture s'annule : jamais une ND émise
        # ACTIVE sur une facture annulée.
        self.api.post(f'/api/django/ventes/notes-debit/{nd_id}/annuler/', {},
                      format='json')
        ok = self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/annuler/', {},
            format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        from apps.ventes.domain.facturation_ops import notes_debit_actives
        self.facture.refresh_from_db()
        self.assertEqual(notes_debit_actives(self.facture), [])
        self.assertTrue(NoteDebit.objects.filter(pk=nd_id).exists())
