"""SCA45 — champs provider-agnostiques sur le chemin Paiement (sol QJ24/NTSUB).

Vérifie :
  * `provider_ref` + `idempotency_key` sont additifs et optionnels (un paiement
    manuel existant reste créable SANS les renseigner — comportement inchangé) ;
  * `idempotency_key` est UNIQUE PAR SOCIÉTÉ quand elle est renseignée : deux
    paiements de la MÊME société avec la même clé → IntegrityError ; deux
    SOCIÉTÉS différentes peuvent réutiliser la même clé ; plusieurs paiements
    SANS clé (null) coexistent librement.
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement


class Sca45PaiementProviderTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='sca45-co', nom='SCA45 Co')
        self.co2 = Company.objects.create(slug='sca45-co2', nom='SCA45 Co2')
        self.cli = Client.objects.create(
            company=self.co, nom='C', prenom='SCA45',
            email='sca45@example.invalid')
        self.cli2 = Client.objects.create(
            company=self.co2, nom='C2', prenom='SCA45',
            email='sca45b@example.invalid')
        self.fac = Facture.objects.create(
            company=self.co, client=self.cli, reference='FAC-SCA45-1',
            statut='emise', taux_tva=Decimal('20'))
        self.fac2 = Facture.objects.create(
            company=self.co2, client=self.cli2, reference='FAC-SCA45-2',
            statut='emise', taux_tva=Decimal('20'))

    def _paiement(self, company, facture, client, **kwargs):
        return Paiement.objects.create(
            company=company, facture=facture, client=client,
            montant=Decimal('1200'), date_paiement=date(2026, 1, 15),
            mode='virement', **kwargs)

    def test_paiement_creatable_without_provider_fields(self):
        """Comportement historique : un paiement manuel sans champs PSP reste
        valide (les deux colonnes sont nulles par défaut)."""
        p = self._paiement(self.co, self.fac, self.cli)
        self.assertIsNone(p.provider_ref)
        self.assertIsNone(p.idempotency_key)

    def test_provider_ref_stored(self):
        p = self._paiement(self.co, self.fac, self.cli,
                           provider_ref='cmi_txn_ABC123')
        p.refresh_from_db()
        self.assertEqual(p.provider_ref, 'cmi_txn_ABC123')

    def test_idempotency_key_unique_per_company(self):
        """Deux paiements de la MÊME société avec la même clé → IntegrityError."""
        self._paiement(self.co, self.fac, self.cli,
                       idempotency_key='evt_777_88')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._paiement(self.co, self.fac, self.cli,
                               idempotency_key='evt_777_88')

    def test_same_idempotency_key_across_companies_ok(self):
        """Deux SOCIÉTÉS peuvent réutiliser la même clé (contrainte scopée)."""
        self._paiement(self.co, self.fac, self.cli,
                       idempotency_key='evt_shared_99')
        # Aucune exception : société différente.
        p2 = self._paiement(self.co2, self.fac2, self.cli2,
                            idempotency_key='evt_shared_99')
        self.assertEqual(p2.idempotency_key, 'evt_shared_99')

    def test_multiple_null_keys_coexist(self):
        """Plusieurs paiements SANS clé (null) coexistent — la contrainte
        n'exclut que les clés renseignées."""
        self._paiement(self.co, self.fac, self.cli)
        self._paiement(self.co, self.fac, self.cli)
        self.assertEqual(
            Paiement.objects.filter(
                company=self.co, idempotency_key__isnull=True).count(), 2)
