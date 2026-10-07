"""Groupe ASTK — lettrage GR/IR (provisions « réceptionné non facturé »).

  * ASTK125 (RESA-8) — une facture fournisseur ne lettre une provision que si
    le cumul facturé du BCF la couvre entièrement : avant, une facture HT de
    100 lettrait une provision de 1 000 ;
  * ASTK126 (RESA-10) — `delettrer_gr_ir_facture` rouvre les seules
    provisions lettrées par la facture, dans sa société.

Services réels (aucun mock) ; le lettrage est appelé comme le fait l'abonné
de ``facture_fournisseur_creee``.

Run :
    python manage.py test apps.installations.tests_astk_gr_ir_lettrage
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations.models_gr_ir import ReceptionNonFacturee
from apps.installations.services import (
    delettrer_gr_ir_facture, lettrer_gr_ir_facture,
)
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
)

User = get_user_model()
_seq = itertools.count(1)


class GrIrBase(TestCase):
    SLUG = 'co-astk-grir'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.SLUG, defaults={'nom': 'Co ASTK GRIR'})
        self.user = User.objects.create_user(
            username=f'resp-{self.SLUG}', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ASTK GRIR')
        self.bc = self.bcf(self.company, self.fournisseur)

    def bcf(self, company, fournisseur):
        return BonCommandeFournisseur.objects.create(
            company=company, fournisseur=fournisseur,
            reference=f'BCF-ASTKGRIR-{next(_seq)}')

    def provision(self, montant, company=None, bc=None):
        return ReceptionNonFacturee.objects.create(
            company=company or self.company, bon_commande=bc or self.bc,
            montant_provision=Decimal(montant))

    def facture(self, montant_ht, company=None, bc=None, fournisseur=None):
        return FactureFournisseur.objects.create(
            company=company or self.company,
            reference=f'FF-ASTKGRIR-{next(_seq)}',
            fournisseur=fournisseur or self.fournisseur,
            bon_commande=bc or self.bc,
            montant_ht=Decimal(montant_ht),
            montant_tva=Decimal(montant_ht) * Decimal('0.2'),
            montant_ttc=Decimal(montant_ht) * Decimal('1.2'))

    def lettrer(self, facture):
        return lettrer_gr_ir_facture(
            facture=facture, company=facture.company, user=self.user)


class LettragePartielTests(GrIrBase):
    SLUG = 'co-astk125'

    def test_facture_partielle_laisse_ouverte(self):
        prov = self.provision('1000')
        self.assertEqual(self.lettrer(self.facture('100')), [])
        prov.refresh_from_db()
        self.assertFalse(prov.lettre)
        self.assertIsNone(prov.facture_id)

    def test_cumul_lettre(self):
        prov = self.provision('1000')
        self.lettrer(self.facture('100'))
        f2 = self.facture('900')
        self.assertEqual(len(self.lettrer(f2)), 1)
        prov.refresh_from_db()
        self.assertTrue(prov.lettre)
        self.assertEqual(prov.facture_id, f2.id)

    def test_ouvertes_egalent_les_receptions_non_facturees(self):
        p1 = self.provision('300')
        p2 = self.provision('700')
        # Facture de 500 : couvre la 1re (300) mais pas la 2e (reste 200).
        self.lettrer(self.facture('500'))
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertTrue(p1.lettre)
        self.assertFalse(p2.lettre)
        # Le complément (500) porte le cumul non lettré à 700 : la 2e passe.
        self.lettrer(self.facture('500'))
        p2.refresh_from_db()
        self.assertTrue(p2.lettre)


class DelettrageTests(GrIrBase):
    SLUG = 'co-astk126'

    def test_delettrer_rouvre_seulement_ses_provisions(self):
        f1 = self.facture('500')
        prov = self.provision('500')
        self.lettrer(f1)
        prov.refresh_from_db()
        self.assertTrue(prov.lettre)
        # Provision d'une autre facture (même société).
        bc2 = self.bcf(self.company, self.fournisseur)
        f2 = self.facture('200', bc=bc2)
        autre = self.provision('200', bc=bc2)
        self.lettrer(f2)
        # Provision d'une autre société, (mal) reliée à la même facture.
        co_b, _ = Company.objects.get_or_create(
            slug='co-astk126-b', defaults={'nom': 'Co ASTK126 B'})
        fourn_b = Fournisseur.objects.create(company=co_b, nom='Fourn B')
        prov_b = ReceptionNonFacturee.objects.create(
            company=co_b, bon_commande=self.bcf(co_b, fourn_b),
            montant_provision=Decimal('500'), lettre=True, facture=f1)

        self.assertEqual(delettrer_gr_ir_facture(f1), 1)

        prov.refresh_from_db()
        self.assertEqual((prov.lettre, prov.date_lettrage, prov.facture_id),
                         (False, None, None))
        autre.refresh_from_db()
        self.assertTrue(autre.lettre)
        self.assertEqual(autre.facture_id, f2.id)
        prov_b.refresh_from_db()
        self.assertTrue(prov_b.lettre)
        self.assertEqual(prov_b.facture_id, f1.id)

    def test_facture_sans_provision_no_op(self):
        self.assertEqual(delettrer_gr_ir_facture(self.facture('50')), 0)
        self.assertEqual(delettrer_gr_ir_facture(None), 0)
