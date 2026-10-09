"""ATOT12 (C-ATOT-019) — `UniqueConstraint(company, reference)` sur
`RemiseEncaissement` : deux remises d'une société ne portent jamais le même
numéro, et le retry de `create_with_reference` joue enfin sur une course.

Rejoue la sonde V1 TNUM-2 : aujourd'hui deux `REM-AAAAMM-0001` identiques
sont acceptées sans erreur. Numérotation réelle (`core.numbering`), aucun
mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_rem_unique"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()


class RemUniqueTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(nom='ATOT12 Co',
                                              slug='atot12-co')
        self.autre = Company.objects.create(nom='ATOT12 Autre',
                                            slug='atot12-autre')
        self.tech = User.objects.create_user(
            username='atot12_tech', password='x', role_legacy='responsable',
            company=self.company)

    def _creer(self, ref, company=None):
        from apps.ventes.models import RemiseEncaissement
        return RemiseEncaissement.objects.create(
            company=company or self.company, technicien=self.tech,
            reference=ref, date_collecte=date.today(),
            montant_declare=Decimal('100.00'))

    def test_meme_reference_refusee(self):
        from apps.ventes.models import RemiseEncaissement
        from apps.ventes.utils.references import next_reference
        ref = next_reference(RemiseEncaissement, 'REM', self.company)
        self.assertEqual(
            next_reference(RemiseEncaissement, 'REM', self.company), ref)
        self._creer(ref)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._creer(ref)
        # Persistance : une seule remise porte ce numéro.
        self.assertEqual(RemiseEncaissement.objects.filter(
            company=self.company, reference=ref).count(), 1)

    def test_retry_create_with_reference(self):
        from apps.ventes.models import RemiseEncaissement
        from apps.ventes.utils.references import (
            create_with_reference, next_reference,
        )
        ref = next_reference(RemiseEncaissement, 'REM', self.company)
        # Une création concurrente a déjà pris `ref`, calculé AVANT elle.
        self._creer(ref)
        appels = []

        def _save(reference):
            appels.append(reference)
            # 1er essai : la référence périmée de la course ; ensuite celle
            # que recalcule create_with_reference.
            return self._creer(ref if len(appels) == 1 else reference)

        remise = create_with_reference(
            RemiseEncaissement, 'REM', self.company, _save,
            padding=4, period='monthly')
        self.assertEqual(len(appels), 2)
        self.assertNotEqual(remise.reference, ref)
        refs = list(RemiseEncaissement.objects.filter(
            company=self.company).values_list('reference', flat=True))
        self.assertEqual(len(refs), len(set(refs)))

    def test_autre_societe_et_vide_autorises(self):
        self._creer('REM-202610-0001')
        self._creer('REM-202610-0001', company=self.autre)
        self._creer('')
        self._creer('')
