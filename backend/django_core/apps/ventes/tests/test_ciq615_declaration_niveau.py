"""CIQ615 — déclaration de raccordement : plus de « MT si triphasé et
≥ 50 kWc » inventé. Le niveau vient de la visite (chantier CIQ610), sinon de
la déclaration (« à confirmer »), sinon il reste VIDE avec la pièce « niveau
de tension à relever ». Assertions sur le HTML RENDU, jamais sur le source.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.installations.models import Installation
from apps.ventes.connection_declaration import (
    build_declaration_data, render_declaration_html)
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

# Hôtel triphasé de 200 kWc (400 panneaux de 500 Wc).
_TRIPHASE_200 = {'n_panneaux': 400, 'puissance_panneau_wc': 500, 'phases': 3}


class _Lead:
    def __init__(self, tension=None, source=None):
        self.tension_raccordement = tension
        self.tension_source = source


class _Devis:
    reference = 'DEV-CIQ615'
    client = None
    etude_params = {}

    def __init__(self, lead=None):
        self.lead = lead


def _html(devis, niveau_chantier=None, regime='accord_raccordement'):
    data = build_declaration_data(
        devis, diagram_params=dict(_TRIPHASE_200), regime_8221=regime,
        niveau_chantier=niveau_chantier)
    return data, render_declaration_html(data)


class NiveauDeclareRenduTest(SimpleTestCase):
    def test_bt_mesure_en_visite(self):
        data, html = _html(_Devis(), {'niveau': 'bt',
                                      'source': 'mesure_visite'})
        self.assertEqual(data['systeme']['kwc'], 200.0)
        self.assertIn('Niveau de raccordement : BT</p>', html)
        self.assertNotIn('MT', html)

    def test_sans_niveau_vide_et_piece_manquante(self):
        data, html = _html(_Devis(_Lead()))
        self.assertEqual(data['raccordement'], '')
        self.assertIn('Niveau de raccordement : —</p>', html)
        self.assertIn('Niveau de tension à relever (BT ou MT)', html)
        self.assertNotIn('Niveau de raccordement : MT', html)

    def test_niveau_seulement_declare(self):
        _data, html = _html(_Devis(_Lead('mt', 'facture')))
        self.assertIn('Niveau de raccordement : MT (à confirmer)</p>', html)
        self.assertNotIn('Niveau de tension à relever', html)

    def test_niveau_chantier_declare_a_confirmer(self):
        _data, html = _html(_Devis(), {'niveau': 'mt', 'source': 'declare'})
        self.assertIn('Niveau de raccordement : MT (à confirmer)</p>', html)

    def test_defaut_du_site_jamais_pris_pour_une_reponse(self):
        data, _html_rendu = _html(_Devis(_Lead('mt', 'site_defaut_visible')))
        self.assertEqual(data['raccordement'], '')

    def test_distributeur_jamais_anre(self):
        _data, html = _html(_Devis())
        self.assertIn('distributeur (ONEE ou SRM régionale)', html)
        self.assertNotIn('ANRE', html)

    def test_hors_reseau_inchange(self):
        data, _html_rendu = _html(_Devis(), regime='declaration_hors_reseau')
        self.assertEqual(data['raccordement'], 'hors réseau')
        self.assertNotIn('niveau_tension_a_relever',
                         {p['code'] for p in data['pieces']})


class NiveauDeclareEndpointTest(TestCase):
    """Le niveau du chantier est lu par ``installations.selectors``."""

    def setUp(self):
        self.company = Company.objects.create(nom='CIQ615', slug='ciq615-co')
        self.user = User.objects.create_user(
            username='ciq615', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        client = Client.objects.create(
            company=self.company, nom='Hôtel', email='ciq615@example.com')
        lead = Lead.objects.create(
            company=self.company, nom='Hôtel', type_installation='commercial',
            tension_raccordement='mt', tension_source='declare')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-CIQ615-10', client=client,
            lead=lead, statut='accepte', taux_tva=Decimal('20'),
            etude_params={'puissance_kwc': 200, 'phases': 3})
        self.url = (f'/api/django/ventes/devis/{self.devis.id}/'
                    'declaration-raccordement/')

    def test_chantier_bt_mesure_prime_sur_le_lead(self):
        Installation.objects.create(
            company=self.company, reference='CHT-CIQ615-10', devis=self.devis,
            type_installation='industriel', niveau_tension='bt',
            niveau_tension_source='mesure_visite')
        resp = self.api.get(self.url, {'regime': 'accord_raccordement'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['raccordement'], 'BT')

    def test_sans_chantier_niveau_declare_du_lead(self):
        resp = self.api.get(self.url, {'regime': 'accord_raccordement'})
        self.assertEqual(resp.data['raccordement'], 'MT (à confirmer)')
