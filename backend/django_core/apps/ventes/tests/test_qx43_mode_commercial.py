"""QX43 — Mode `commercial` de bout en bout côté ERP.

Couvre :
  - Le choix ModeInstallation.COMMERCIAL existe et le label INDUSTRIEL redevient
    « Industriel » (plus « Industriel / Commercial »).
  - PAYMENT_TERMS_BY_MODE['commercial'] = 50/40/10 (comme industriel).
  - _FINANCING_PROGRAMS route commercial → Tatwir (réutilise l'industriel).
  - build_quote_data d'un devis commercial : inst_type = « Commerciale »
    (jamais un repli résidentiel silencieux) + payment_terms 50/40/10.
  - Non-régression : residentiel/industriel/agricole inchangés.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx43_mode_commercial -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import (
    PAYMENT_TERMS_BY_MODE, _FINANCING_PROGRAMS, compute_financing_block,
)
from apps.ventes.utils.company_settings import payment_terms_for


def make_company(slug='test-qx43'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test QX43'})
    return company


def make_user(company):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = f'qx43_{company.slug}'
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=username, password='x',
            role_legacy='responsable', company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Hôtel Atlas', prenom='Direction',
        email=f'c_{company.slug}@example.com', telephone='+212611000001')


def make_devis_with_lines(company, user, client, lines, ref, mode):
    devis = Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user,
        mode_installation=mode)
    for i, (desig, qty, pu) in enumerate(lines):
        p = Produit.objects.create(
            company=company, nom=desig, sku=f"QX43-{ref[-4:]}-{i}",
            prix_vente=Decimal(str(pu)), prix_achat=Decimal('1'),
            quantite_stock=100)
        LigneDevis.objects.create(
            devis=devis, produit=p, designation=desig,
            quantite=Decimal(str(qty)), prix_unitaire=Decimal(str(pu)),
            remise=Decimal('0'))
    return devis


class TestModeChoiceExists(TestCase):
    def test_commercial_choice_present(self):
        values = dict(Devis.ModeInstallation.choices)
        self.assertIn('commercial', values)
        self.assertEqual(values['commercial'], 'Commercial')

    def test_industriel_label_no_longer_mentions_commercial(self):
        values = dict(Devis.ModeInstallation.choices)
        self.assertEqual(values['industriel'], 'Industriel')

    def test_all_four_modes_present(self):
        values = set(dict(Devis.ModeInstallation.choices))
        self.assertEqual(
            values, {'residentiel', 'industriel', 'commercial', 'agricole'})


class TestCommercialMaps(TestCase):
    def test_payment_terms_commercial_50_40_10(self):
        self.assertEqual(
            PAYMENT_TERMS_BY_MODE['commercial'],
            {'acompte': 50, 'materiel': 40, 'solde': 10})

    def test_payment_terms_industriel_unchanged(self):
        self.assertEqual(
            PAYMENT_TERMS_BY_MODE['industriel'],
            {'acompte': 50, 'materiel': 40, 'solde': 10})

    def test_financing_commercial_routes_to_tatwir(self):
        self.assertIn('commercial', _FINANCING_PROGRAMS)
        self.assertEqual(
            _FINANCING_PROGRAMS['commercial']['programme_label'], 'Tatwir')

    def test_compute_financing_commercial_tatwir(self):
        result = compute_financing_block(300_000, 30_000, 40_000, 'commercial')
        self.assertEqual(result['credit']['programme_label'], 'Tatwir')

    def test_payment_terms_for_commercial(self):
        company = make_company('qx43-pt')
        self.assertEqual(
            payment_terms_for(company, 'commercial'),
            {'acompte': 50, 'materiel': 40, 'solde': 10})


class TestCommercialBuildQuoteData(TestCase):
    def setUp(self):
        self.company = make_company('qx43-bqd')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _build(self, mode, ref):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis_with_lines(
            self.company, self.user, self.client_obj,
            [('Panneau Jinko 710W', '20', '2000'),
             ('Onduleur réseau Huawei 20kW', '1', '30000')],
            ref=ref, mode=mode)
        return build_quote_data(devis)

    def test_commercial_inst_type_is_commerciale(self):
        """Un devis commercial NE tombe PAS dans un libellé résidentiel."""
        data = self._build('commercial', 'DEV-QX43-COM-1')
        self.assertEqual(data['inst_type'], 'Commerciale')
        self.assertEqual(data['mode_installation'], 'commercial')

    def test_commercial_payment_terms_50_40_10(self):
        data = self._build('commercial', 'DEV-QX43-COM-2')
        self.assertEqual(
            data['payment_terms'],
            {'acompte': 50, 'materiel': 40, 'solde': 10})

    def test_industriel_inst_type_no_longer_slash_commerciale(self):
        data = self._build('industriel', 'DEV-QX43-IND-1')
        self.assertEqual(data['inst_type'], 'Industrielle')

    def test_residentiel_still_residentielle(self):
        data = self._build('residentiel', 'DEV-QX43-RES-1')
        self.assertEqual(data['inst_type'], 'Résidentielle')

    def test_agricole_still_agricole(self):
        data = self._build('agricole', 'DEV-QX43-AGR-1')
        self.assertEqual(data['inst_type'], 'Agricole')
