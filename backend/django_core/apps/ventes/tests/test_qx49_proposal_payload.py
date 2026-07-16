"""QX49 — Payload proposition mode-complet.

Le payload public expose mode_installation, categorie_commerciale et un bloc KPI
par mode (pompage : pompe_cv/kw, hmt, débit, m³/jour, champ kWc, bassin, FDA ;
industriel/commercial : autoconso/couverture/économies/payback + injection 82-21
si calculée). Whitelist STRICTE — jamais prix_achat/marge (RULE #4).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx49_proposal_payload -v 2
"""
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import _mode_kpis

User = get_user_model()


class TestModeKpisPure(SimpleTestCase):
    def test_agricole_kpis(self):
        data = {
            'mode_installation': 'agricole',
            'puissance_kwc': 9.24,
            'etude': {
                'pompe_cv': '7.5', 'pompe_kw': 5.5, 'hmt_m': 60,
                'debit_hmt_m3h': 16, 'm3_jour': 112, 'champ_kwc': 9.24,
                'irrigation_method': 'goutte', 'crop': 'agrumes',
                'region': 'souss-massa', 'surface_ha': 2,
            },
        }
        k = _mode_kpis(data)
        self.assertEqual(k['pompe_cv'], 7.5)
        self.assertEqual(k['hmt_m'], 60)
        self.assertEqual(k['m3_jour'], 112)
        self.assertEqual(k['champ_kwc'], 9.24)
        self.assertTrue(k['fda_eligible'])          # goutte → éligible
        self.assertIsNotNone(k['bassin_m3'])        # dérivé du besoin FAO-56

    def test_agricole_fda_not_eligible_without_drip(self):
        data = {'mode_installation': 'agricole',
                'etude': {'irrigation_method': 'gravitaire'}}
        self.assertFalse(_mode_kpis(data)['fda_eligible'])

    def test_industriel_kpis(self):
        data = {'mode_installation': 'industriel',
                'etude': {'taux_autoconso': 88, 'taux_couverture': 67.7,
                          'economies_annuelles': 420000, 'payback': 3.1}}
        k = _mode_kpis(data)
        self.assertEqual(k['taux_autoconso'], 88)
        self.assertEqual(k['economies_annuelles'], 420000)
        self.assertIsNone(k['injection_dh_an'])     # pas d'injection → None

    def test_commercial_kpis_with_injection(self):
        data = {'mode_installation': 'commercial',
                'etude': {'taux_autoconso': 78, 'taux_couverture': 59,
                          'economies_annuelles': 165000, 'payback': 3.4,
                          'injection_kwh_an': 45000, 'injection_dh_an': 30000}}
        k = _mode_kpis(data)
        self.assertEqual(k['injection_dh_an'], 30000)
        self.assertEqual(k['injection_kwh_an'], 45000)

    def test_residentiel_returns_none(self):
        self.assertIsNone(_mode_kpis({'mode_installation': 'residentiel', 'etude': {}}))
        self.assertIsNone(_mode_kpis({'mode_installation': '', 'etude': {}}))

    def test_no_buy_price_in_kpis(self):
        data = {'mode_installation': 'industriel',
                'etude': {'taux_autoconso': 88, 'prix_achat': 999, 'marge': 50}}
        blob = json.dumps(_mode_kpis(data))
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)
        self.assertNotIn('999', blob)


def _make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


class TestProposalPayloadModes(TestCase):
    def setUp(self):
        self.company = _make_company('qx49-ep')
        self.user = User.objects.create_user(
            username='qx49', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Atlas', prenom='Com',
            email='c_qx49@ex.com', telephone='+212600000049')

    def _devis(self, ref, mode, etude):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            mode_installation=mode, etude_params=etude)
        for desig, qty, pu in [('Onduleur réseau 8kW', '1', '14000'),
                               ('Panneau mono 550W', '10', '1400')]:
            p = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{ref[-6:]}-{desig[:8]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('9999'),
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=p, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=self.company, devis=devis, token=token)
        return DjangoClient().get(f'/api/django/public/proposal/{token}/data/')

    def test_commercial_payload_has_mode_and_category(self):
        devis = self._devis('DEV-QX49-COM', 'commercial', {
            'categorie_commerciale': 'hotel', 'taux_autoconso': 78,
            'taux_couverture': 59, 'economies_annuelles': 165000, 'payback': 3.4})
        resp = self._payload(devis)
        self.assertEqual(resp.status_code, 200)
        p = resp.json()
        self.assertEqual(p['mode_installation'], 'commercial')
        self.assertEqual(p['categorie_commerciale'], 'hotel')
        self.assertIsNotNone(p['mode_kpis'])
        self.assertEqual(p['mode_kpis']['taux_autoconso'], 78)
        # RULE #4 — jamais de prix d'achat / marge dans tout le payload
        blob = json.dumps(p)
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('9999', blob)

    def test_industriel_payload_kpis(self):
        devis = self._devis('DEV-QX49-IND', 'industriel', {
            'taux_autoconso': 88, 'taux_couverture': 67,
            'economies_annuelles': 420000, 'payback': 3.1})
        p = self._payload(devis).json()
        self.assertEqual(p['mode_installation'], 'industriel')
        self.assertIsNone(p['categorie_commerciale'])
        self.assertEqual(p['mode_kpis']['payback'], 3.1)
