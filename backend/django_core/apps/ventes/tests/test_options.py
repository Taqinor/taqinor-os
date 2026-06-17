"""Tests A3 — l'option acceptée est autoritative en aval (facture + chantier).

Un devis à deux options (réseau + hybride/batterie) accepté « Sans batterie »
doit facturer et gélifier la nomenclature SUR LES SEULES lignes sans batterie ;
« Avec batterie » sur les seules lignes avec batterie ; un devis à option unique
reste strictement inchangé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import (
    filter_lines_for_option, option_lines, option_totaux,
)
from apps.ventes.utils.echeancier import next_tranche
from apps.installations.services import _freeze_bom

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class _StubLigne:
    def __init__(self, designation, nom=''):
        self.designation = designation
        self.produit = type('P', (), {'nom': nom})()


class TestPureFilter(SimpleTestCase):
    """Découpage PUR (pas de base) — garde rapide de la classification."""

    def setUp(self):
        self.lignes = [
            _StubLigne('Onduleur réseau 5kW'),
            _StubLigne('Onduleur hybride 5kW'),
            _StubLigne('Panneau mono 550W', nom='Jinko'),
            _StubLigne('Batterie lithium 5 kWh'),
            _StubLigne('Installation complète'),
        ]

    def _names(self, rows):
        return [r.designation for r in rows]

    def test_sans_batterie_drops_battery_and_hybrid(self):
        names = self._names(filter_lines_for_option(self.lignes, 'sans_batterie'))
        self.assertIn('Onduleur réseau 5kW', names)
        self.assertIn('Panneau mono 550W', names)
        self.assertNotIn('Batterie lithium 5 kWh', names)
        self.assertNotIn('Onduleur hybride 5kW', names)

    def test_avec_batterie_drops_reseau(self):
        names = self._names(filter_lines_for_option(self.lignes, 'avec_batterie'))
        self.assertNotIn('Onduleur réseau 5kW', names)
        self.assertIn('Onduleur hybride 5kW', names)
        self.assertIn('Batterie lithium 5 kWh', names)

    def test_empty_option_keeps_all(self):
        self.assertEqual(len(filter_lines_for_option(self.lignes, '')), 5)


class TestOptionDownstream(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='opt-co', defaults={'nom': 'Opt Co'})
        self.user = User.objects.create_user(
            username='opt_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Opt',
            email='opt@example.com', telephone='+212600000009')

    def _two_option_devis(self, num=40):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        lignes = [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ]
        for desig, qty, pu in lignes:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{num}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _single_option_devis(self, num=50):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        for desig, qty, pu in [
            ('Onduleur réseau', '1', '11700'),
            ('Panneau mono 550W', '14', '1100'),
        ]:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{num}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_option_totaux_sans(self):
        devis = self._two_option_devis(num=41)
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['option_acceptee'])
        t = option_totaux(devis)
        # réseau 11700 + panneaux 15400 + installation 4000 = 31100 HT
        self.assertEqual(t['ht'], Decimal('31100'))
        self.assertEqual(t['tva'], Decimal('6220.00'))
        self.assertEqual(t['ttc'], Decimal('37320.00'))

    def test_option_totaux_avec(self):
        devis = self._two_option_devis(num=42)
        devis.option_acceptee = 'avec_batterie'
        devis.save(update_fields=['option_acceptee'])
        t = option_totaux(devis)
        # hybride 24000 + panneaux 15400 + batterie 14000 + installation 4000
        self.assertEqual(t['ht'], Decimal('57400'))
        self.assertEqual(t['ttc'], Decimal('68880.00'))

    def test_echeancier_acompte_uses_accepted_option(self):
        devis = self._two_option_devis(num=43)
        devis.option_acceptee = 'sans_batterie'
        devis.statut = Devis.Statut.ACCEPTE
        devis.save(update_fields=['option_acceptee', 'statut'])
        tr = next_tranche(devis)
        # acompte 30 % du TTC de l'option « sans » (37320), pas du total mêlé.
        self.assertEqual(tr['key'], 'acompte')
        self.assertEqual(tr['ttc'], Decimal('11196.00'))

    def test_bom_excludes_battery_for_sans(self):
        devis = self._two_option_devis(num=44)
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['option_acceptee'])
        designations = [li['designation'] for li in _freeze_bom(devis)]
        self.assertIn('Onduleur réseau', designations)
        self.assertNotIn('Batterie 5 kWh', designations)
        self.assertNotIn('Onduleur hybride', designations)

    def test_bom_includes_battery_for_avec(self):
        devis = self._two_option_devis(num=45)
        devis.option_acceptee = 'avec_batterie'
        devis.save(update_fields=['option_acceptee'])
        designations = [li['designation'] for li in _freeze_bom(devis)]
        self.assertIn('Batterie 5 kWh', designations)
        self.assertIn('Onduleur hybride', designations)
        self.assertNotIn('Onduleur réseau', designations)

    def test_single_option_unchanged(self):
        """Devis à option unique : option_totaux = totaux complets, BOM complet,
        même si une option est posée (déduite). Comportement historique."""
        devis = self._single_option_devis(num=51)
        devis.option_acceptee = 'sans_batterie'  # déduite par A1
        devis.save(update_fields=['option_acceptee'])
        t = option_totaux(devis)
        self.assertEqual(t['ht'], Decimal(str(devis.total_ht)))
        self.assertEqual(t['ttc'], Decimal(str(devis.total_ttc)))
        self.assertEqual(len(option_lines(devis)), 2)
