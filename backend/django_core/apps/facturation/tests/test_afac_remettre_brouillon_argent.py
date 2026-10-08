"""AFAC11 (C-AFAC-004) — « Remettre en brouillon » n'est permis que sur une
facture SANS argent rattaché (paiements, avances ventilées, notes de débit,
retenues subies, avoirs actifs), sous verrou, en révoquant le lien de paiement
actif.

Rejoue la sonde FBC-4 (avance ventilée / note de débit / RAS : 200 ; lien
toujours en_attente). Endpoint, services et modèles réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_remettre_brouillon_argent"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class RemettreBrouillonArgentTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC11 Co', slug=f'afac11-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac11_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Brouillon', prenom='AFAC11',
            email=f'afac11-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        from apps.ventes.models import Facture
        ttc = Decimal('50000')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC11-{_nxt():04d}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def _remettre(self):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/remettre-brouillon/',
            {}, format='json')

    def _assert_refus_intact(self, r, nature):
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(nature, r.data['detail'])
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, 'emise')
        self.assertEqual(self.facture.total_ttc, Decimal('50000'))

    def test_avance_ventilee_refuse(self):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('30000'), date_paiement=date(2026, 10, 1),
            mode='virement', created_by=self.user)
        ventiler_avance(paiement=avance, facture=self.facture,
                        montant=Decimal('30000'), user=self.user)
        self.assertFalse(self.facture.paiements.exists())
        r = self._remettre()
        self._assert_refus_intact(r, 'avances ventilées')
        self.assertEqual(
            self.facture.affectations_paiement.count(), 1)

    def test_note_debit_refuse(self):
        from apps.ventes.models import NoteDebit
        NoteDebit.objects.create(
            company=self.company, reference=f'ND-AFAC11-{_nxt()}',
            facture=self.facture, client=self.client_obj, statut='emise',
            motif='Complément', montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        r = self._remettre()
        self._assert_refus_intact(r, 'notes de débit')

    def test_retenue_refuse(self):
        from apps.ventes.models import RetenueSubie
        RetenueSubie.objects.create(
            company=self.company, facture=self.facture,
            type_retenue='ras_tva', taux=Decimal('75'),
            base=Decimal('8333.33'), montant=Decimal('6250'))
        r = self._remettre()
        self._assert_refus_intact(r, 'retenues')

    def test_lien_actif_revoque(self):
        from apps.ventes.domain.encaissements import create_payment_link
        from apps.ventes.models import PaymentLink
        lien = create_payment_link(facture=self.facture)
        self.assertEqual(lien.statut, PaymentLink.Statut.EN_ATTENTE)
        r = self._remettre()
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        lien.refresh_from_db()
        self.assertEqual(self.facture.statut, 'brouillon')
        self.assertEqual(lien.statut, PaymentLink.Statut.ANNULE)
        # CLAUSE CLIENT : la page publique ne propose plus de payer.
        pub = APIClient().get(f'/api/django/public/pay/{lien.token}/')
        if pub.status_code == 200:
            self.assertEqual(pub.data['statut'], 'annule')
            self.assertTrue(pub.data['expire'])
        else:
            self.assertEqual(pub.status_code, 404)
