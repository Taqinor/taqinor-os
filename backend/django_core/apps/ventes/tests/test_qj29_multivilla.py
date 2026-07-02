"""QJ29 — Multi-property quote data model + totals.

(A) ×N identical villas — whole-quote multiplier etude_params['nombre_proprietes']
    (default 1) scaling HT/TVA/TTC + production/économies in build_quote_data.
(B) different villas — additive nullable LigneDevis.groupe_index + groupe_label
    so lines partition into per-villa groups (0 = commun) with per-villa
    subtotals + one grand total via _canonical_totaux in selectors.py.
NO devis splitting — one document. The single-system path is unchanged when
these fields are unused.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj29_multivilla -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company():
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(
        slug='test-qj29-co', defaults={'nom': 'Test QJ29 Co'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qj29user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Villa', prenom='Owner',
        email='v@example.com', telephone='+212600000009')


def _produit(company, desig, sku, pu):
    return Produit.objects.create(
        company=company, nom=desig, sku=sku, prix_vente=Decimal(pu),
        prix_achat=Decimal('1'), quantite_stock=100)


class TestNombreProprietesMultiplier(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, etude_params, reference):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            etude_params=etude_params)
        for desig, qty, pu in [('Onduleur réseau 8kW', '1', '14000'),
                               ('Panneau mono 550W', '10', '1400')]:
            LigneDevis.objects.create(
                devis=devis,
                produit=_produit(self.company, desig,
                                 f'{reference[-6:]}-{desig[:8]}', pu),
                designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), remise=Decimal('0'))
        return devis

    def test_default_n1_is_noop(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis({'scenario': 'Sans batterie'}, 'DEV-QJ29-N1')
        data = build_quote_data(devis)
        # No multi keys when N == 1 (single-system path unchanged).
        self.assertNotIn('nombre_proprietes', data)
        self.assertNotIn('totaux_multi', data)

    def test_n_scales_totals_and_production(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            {'scenario': 'Sans batterie', 'nombre_proprietes': 3},
            'DEV-QJ29-N3')
        data = build_quote_data(devis)
        self.assertEqual(data['nombre_proprietes'], 3)
        self.assertEqual(data['display_total_multi'],
                         round(data['display_total_unitaire'] * 3))
        # totals scaled ×3
        self.assertEqual(data['totaux_multi']['all']['ttc'],
                         round(data['totaux_all']['ttc'] * 3))
        # production + savings scaled ×3
        self.assertEqual(data['prod_kwh_multi'], data['prod_kwh'] * 3)
        self.assertEqual(data['eco_s_ann_multi'], data['eco_s_ann'] * 3)

    def test_invalid_n_defaults_to_one(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._devis(
            {'scenario': 'Sans batterie', 'nombre_proprietes': 'x'},
            'DEV-QJ29-BAD')
        data = build_quote_data(devis)
        self.assertNotIn('nombre_proprietes', data)


class TestGroupedVillaTotals(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _grouped_devis(self, reference='DEV-QJ29-GRP'):
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        # commun (0), Villa A (1), Villa B (2)
        rows = [
            ('Installation commune', '1', '5000', 0, 'Équipement commun'),
            ('Onduleur réseau 8kW', '1', '14000', 1, 'Villa A'),
            ('Panneau mono 550W', '10', '1400', 1, 'Villa A'),
            ('Onduleur réseau 5kW', '1', '11000', 2, 'Villa B'),
            ('Panneau mono 550W', '8', '1400', 2, 'Villa B'),
        ]
        for i, (desig, qty, pu, gi, gl) in enumerate(rows):
            LigneDevis.objects.create(
                devis=devis,
                produit=_produit(self.company, desig,
                                 f'{reference[-6:]}-{i}', pu),
                designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                groupe_index=gi, groupe_label=gl)
        return devis

    def test_selector_returns_per_villa_and_grand_total(self):
        from apps.ventes.selectors import multi_villa_totaux
        devis = self._grouped_devis()
        mv = multi_villa_totaux(devis)
        self.assertIsNotNone(mv)
        labels = [g['label'] for g in mv['groupes']]
        self.assertEqual(labels, ['Équipement commun', 'Villa A', 'Villa B'])
        # per-villa HT
        commun = mv['groupes'][0]['totaux']['ht_brut']
        villa_a = mv['groupes'][1]['totaux']['ht_brut']
        villa_b = mv['groupes'][2]['totaux']['ht_brut']
        self.assertEqual(commun, Decimal('5000.00'))
        self.assertEqual(villa_a, Decimal('28000.00'))   # 14000 + 10*1400
        self.assertEqual(villa_b, Decimal('22200.00'))   # 11000 + 8*1400
        # grand total HT = sum of all groups
        self.assertEqual(mv['grand_total']['ht_brut'],
                         commun + villa_a + villa_b)

    def test_ungrouped_devis_returns_none(self):
        from apps.ventes.selectors import multi_villa_totaux
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJ29-FLAT',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user)
        LigneDevis.objects.create(
            devis=devis,
            produit=_produit(self.company, 'X', 'QJ29-FLAT-0', '1000'),
            designation='X', quantite=Decimal('1'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'))
        self.assertIsNone(multi_villa_totaux(devis))

    def test_build_quote_data_exposes_multi_villa(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = self._grouped_devis('DEV-QJ29-BQD')
        data = build_quote_data(devis)
        self.assertIn('multi_villa', data)
        self.assertEqual(len(data['multi_villa']['groupes']), 3)
        gt = data['multi_villa']['grand_total']['ht_brut']
        self.assertAlmostEqual(gt, 5000 + 28000 + 22200, places=2)


class TestSingleSystemUnchanged(TestCase):
    """A plain quote (no groups, no N) exposes none of the QJ29 keys."""

    def test_no_qj29_keys_on_plain_quote(self):
        from apps.ventes.quote_engine import build_quote_data
        company = make_company()
        user = make_user(company)
        client_obj = make_client(company)
        devis = Devis.objects.create(
            company=company, reference='DEV-QJ29-PLAIN', client=client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=user,
            etude_params={'scenario': 'Sans batterie'})
        LigneDevis.objects.create(
            devis=devis,
            produit=_produit(company, 'Onduleur réseau 8kW', 'PLAIN-0', '14000'),
            designation='Onduleur réseau 8kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'))
        data = build_quote_data(devis)
        for k in ('nombre_proprietes', 'totaux_multi', 'multi_villa',
                  'display_total_multi'):
            self.assertNotIn(k, data)
