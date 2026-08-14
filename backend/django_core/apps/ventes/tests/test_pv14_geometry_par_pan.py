"""PV14 — ``extract_roof_config`` lit la géométrie PAR PAN des layouts v1.

Les layouts déjà stockés par roofPro11 (sérialisation v1) ne portent PAS de
bloc ``result`` par zone : la puissance et le compte RÉELS vivent dans le bloc
``geometry`` de la zone (WJ24). Sans cette lecture, un tel blob remontait
0 kWc — et ``build_devis_from_layout`` ne pouvait plus déduire le wattage du
panneau (donc plus de choix de produit à wattage exact).

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_pv14_geometry_par_pan -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.services import build_devis_from_layout, extract_roof_config

User = get_user_model()


def _zone_v1(zid, *, kwc, count, needed, azimut=0.0, pitch=15.0):
    """Zone telle que sérialisée par roofPro11 v1 : PAS de ``result``, un bloc
    ``geometry`` complet (WJ24) et le ``neededPanels`` historique."""
    return {
        'id': zid,
        'label': f'Pan {zid}',
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'pitched',
        'pitchDeg': pitch,
        'facingAzimuthDeg': azimut,
        'facingManual': False,
        'neededPanels': needed,
        'neededAuto': True,
        'geometry': {
            'azimuthDeg': 180.0,
            'tiltDeg': pitch,
            'family': 'south',
            'flush': True,
            'kwc': kwc,
            'count': count,
            'origin': [-7.6, 33.5],
            'panels': [{'cx': i * 1.2, 'cy': 0.0} for i in range(count)],
        },
    }


class TestExtractRoofConfigGeometrie(SimpleTestCase):
    """Agrégation pure — aucune base de données."""

    def test_blob_v1_sans_result_agrege_la_geometrie(self):
        layout = {
            'version': 1,
            'pin': {'lat': 33.5, 'lng': -7.6},
            'outline': [],
            'billKwh': None,
            'activeAreaId': 'z1',
            'zones': [
                _zone_v1('z1', kwc=6.6, count=12, needed=12),
                _zone_v1('z2', kwc=3.3, count=6, needed=6, azimut=90.0),
            ],
        }
        cfg = extract_roof_config(layout)
        self.assertEqual(cfg['nb_pans'], 2)
        self.assertAlmostEqual(cfg['kwc'], 9.9, places=3)
        self.assertEqual(cfg['nb_panneaux'], 18)
        # Le pan le plus puissant donne l'orientation principale.
        self.assertEqual(cfg['pans'][0]['kwc'], 6.6)
        self.assertEqual(cfg['pans'][0]['nb_panneaux'], 12)

    def test_geometry_prime_sur_neededpanels(self):
        """``neededPanels`` = compte SOUHAITÉ ; ``geometry.count`` = compte POSÉ."""
        layout = {'zones': [_zone_v1('z1', kwc=5.5, count=10, needed=14)]}
        cfg = extract_roof_config(layout)
        self.assertEqual(cfg['nb_panneaux'], 10)

    def test_result_prime_toujours_sur_geometry(self):
        """Aucune régression : un pan porteur d'un ``result`` garde SES chiffres."""
        zone = _zone_v1('z1', kwc=5.5, count=10, needed=14)
        zone['result'] = {'count': 20, 'kwc': 11.0, 'areaM2': 42.0}
        cfg = extract_roof_config({'zones': [zone]})
        self.assertEqual(cfg['nb_panneaux'], 20)
        self.assertAlmostEqual(cfg['kwc'], 11.0, places=3)
        self.assertAlmostEqual(cfg['surface_m2'], 42.0, places=2)

    def test_neededpanels_reste_le_dernier_recours(self):
        """Ni ``result`` ni ``geometry`` → l'ancien repli tient toujours."""
        zone = _zone_v1('z1', kwc=5.5, count=10, needed=14)
        zone.pop('geometry')
        cfg = extract_roof_config({'zones': [zone]})
        self.assertEqual(cfg['nb_panneaux'], 14)
        self.assertEqual(cfg['kwc'], 0.0)

    def test_geometry_non_dict_est_ignoree_sans_exception(self):
        zone = _zone_v1('z1', kwc=5.5, count=10, needed=14)
        zone['geometry'] = 'corrompu'
        cfg = extract_roof_config({'zones': [zone]})
        self.assertEqual(cfg['nb_panneaux'], 14)


class TestBuildDevisDepuisBlobV1(TestCase):
    """Effet aval : le wattage panneau redevient déductible → produit exact."""

    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='pv14-co', defaults={'nom': 'PV14'})
        self.user = User.objects.create_user(
            username='pv14user', password='x', role_legacy='responsable',
            company=self.company)
        # Deux panneaux : le MOINS CHER n'est PAS celui du bon wattage — c'est
        # ce qui rend le chemin « wattage exact » observable.
        Produit.objects.create(
            company=self.company, nom='Panneau Longi 450W', sku='PAN450',
            prix_vente=Decimal('900'), prix_achat=Decimal('1'),
            quantite_stock=100)
        Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PAN550',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=100)
        Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW Monophasé',
            sku='ONDR', prix_vente=Decimal('14000'),
            prix_achat=Decimal('1'), quantite_stock=100)

    def _lead(self):
        return Lead.objects.create(
            company=self.company, nom='Toit', prenom='V1',
            email='v1@example.com')

    def test_blob_v1_resout_un_panneau_au_wattage_exact(self):
        # 12 panneaux, 6.6 kWc → 550 Wc par panneau.
        layout = {
            'version': 1,
            'scenario': 'reseau',
            'zones': [_zone_v1('z1', kwc=6.6, count=12, needed=12)],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        panneaux = [li for li in devis.lignes.all()
                    if 'Panneau' in li.designation]
        self.assertEqual(len(panneaux), 1)
        self.assertEqual(panneaux[0].designation, 'Panneau Jinko 550W')
        self.assertEqual(int(panneaux[0].quantite), 12)
        # kWc agrégé remonté dans l'étude, jamais 0.
        self.assertAlmostEqual(
            float(devis.etude_params['puissance_kwc']), 6.6, places=3)
        self.assertEqual(devis.etude_params['toiture']['nb_panneaux'], 12)
        # Le service ne touche JAMAIS au statut (règle #4).
        self.assertEqual(devis.statut, 'brouillon')

    def test_multi_pans_v1_somme_les_panneaux(self):
        layout = {
            'version': 1,
            'scenario': 'reseau',
            'zones': [
                _zone_v1('z1', kwc=6.6, count=12, needed=12),
                _zone_v1('z2', kwc=3.3, count=6, needed=6, azimut=90.0),
            ],
        }
        devis = build_devis_from_layout(
            layout=layout, user=self.user, company=self.company,
            lead=self._lead())
        panneau = next(li for li in devis.lignes.all()
                       if 'Panneau' in li.designation)
        self.assertEqual(int(panneau.quantite), 18)
        self.assertEqual(panneau.designation, 'Panneau Jinko 550W')
        self.assertAlmostEqual(
            float(devis.etude_params['puissance_kwc']), 9.9, places=3)
