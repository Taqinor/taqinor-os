"""PV77 — l'étude bancable côté CLIENT : deux chiffres, et rien d'autre.

La simulation (PV69/PV74) est un outil d'INGÉNIERIE. Le client a droit au
chiffre honnête de production (P50) et à l'économie 25 ans que le document
affiche déjà ; le reste — P90/P75, arbre de pertes, VAN/TRI, puissance
souscrite recommandée — reste interne au vendeur (PDF signé + écran ERP).

Trois garanties verrouillées ici :

  1. **Sans simulation, la charge utile publique ne bouge pas d'un octet** :
     aucune clé ``bankable``, aucune clé retirée.
  2. **Avec simulation**, la clé ``bankable`` apparaît avec EXACTEMENT
     ``p50_kwh`` / ``economies_25_ans`` / ``source``.
  3. **Rien d'interne ne fuit** : ni la clé brute ``simulation`` (qui transitait
     jusqu'ici dans ``quote.etude``), ni P90/P75, ni la décomposition des
     pertes, ni la VAN/le TRI — vérifié RÉCURSIVEMENT sur tout le JSON servi.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv77_proposition_bancable -v 2
"""
import json
import uuid
from decimal import Decimal

from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from authentication.models import Company

SIMULATION = {
    'version': 1,
    'computed_at': '2026-08-14T10:00:00Z',
    'source': 'pvgis',
    'zones': [{'label': 'Pan Sud', 'lat': 33.57, 'lon': -7.59, 'tilt': 30,
               'azimuth': 0, 'kwc': 42.3, 'base_production_kwh': 71800,
               'shading_annual_loss_pct': 4.2}],
    'pr': {
        'performance_ratio': 0.812, 'total_loss_pct': 18.8,
        'loss_breakdown': {'temperature': 8.0, 'soiling': 3.0, 'shading': 4.2,
                           'wiring': 2.0, 'inverter': 2.5, 'mismatch': 2.0,
                           'availability': 1.0},
        # Valeurs volontairement « improbables » : les retrouver dans le JSON
        # public ne peut alors être qu'une FUITE, jamais une coïncidence.
        'p50_kwh': 71800, 'p90_kwh': 58317, 'p75_kwh': 66413,
        'annual_variability': 0.06, 'specific_yield_kwh_kwc': 1697,
    },
    'self_consumption': {'hours': 8760, 'self_consumption_rate': 0.41,
                         'coverage_rate': 0.63, 'self_consumed_kwh': 29400,
                         'surplus_kwh': 42400, 'grid_import_kwh': 17300},
    'net_metering': {'annual_savings_mad': 33800,
                     'annual_compensated_kwh': 24100,
                     'annual_spill_value_mad': 0},
    'subscribed_power': {'peak_reduction_pct': 22.0,
                         'recommended_subscribed': 68, 'annual_saving': 5200},
    'degradation': {'factor_year1': 0.9784, 'factor_last_year': 0.874,
                    'any_warranty_breach': False},
    'projection_25y': {'npv': 412337, 'irr': 0.18731, 'payback_year': 6,
                       'discounted_payback_year': 7},
    'warnings': [],
}

#: Noms de clés qui ne doivent JAMAIS apparaître dans le JSON public.
CLES_INTERDITES = (
    'simulation', 'bankable_pr', 'loss_breakdown', 'p90_kwh', 'p75_kwh',
    'performance_ratio', 'total_loss_pct', 'npv', 'irr', 'subscribed_power',
    'recommended_subscribed', 'annual_variability', 'projection_25y',
    'specific_yield_kwh_kwc',
)

#: Valeurs internes reconnaissables (elles ne figurent nulle part ailleurs
#: dans un devis de test : les retrouver dans le JSON = une fuite).
VALEURS_INTERDITES = ('58317', '66413', '412337', '0.18731')


def cles_profondes(obj):
    """Toutes les clés de dict, à N'IMPORTE QUELLE profondeur."""
    vues = set()
    if isinstance(obj, dict):
        for clef, valeur in obj.items():
            vues.add(clef)
            vues |= cles_profondes(valeur)
    elif isinstance(obj, (list, tuple)):
        for valeur in obj:
            vues |= cles_profondes(valeur)
    return vues


class PropositionBancableTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Acme', slug='pv77-acme')
        self.crm_client = Client.objects.create(
            company=self.company, nom='Client PV77', email='pv77@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DV-PV77-1',
            client=self.crm_client, mode_installation='industriel',
            etude_params={'production_annuelle': 12486,
                          'conso_annuelle': 120000,
                          'economies_annuelles': 21851, 'payback': 3.0})
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV 550W mono', sku='PV77-PAN',
            prix_vente=Decimal('1234'), prix_achat=Decimal('789'),
            quantite_stock=100)
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 10kW triphasé',
            sku='PV77-OND', prix_vente=Decimal('12345'),
            prix_achat=Decimal('9876'), quantite_stock=10)
        LigneDevis.objects.create(
            devis=self.devis, produit=panneau,
            designation='Panneau PV 550W mono', quantite=14,
            prix_unitaire=Decimal('1234'))
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur,
            designation='Onduleur réseau 10kW triphasé', quantite=1,
            prix_unitaire=Decimal('12345'))

    def _simuler(self):
        """Pose l'étude bancable sur le devis (ce que fait PV74 après calcul)."""
        etude = dict(self.devis.etude_params or {})
        etude['simulation'] = SIMULATION
        self.devis.etude_params = etude
        self.devis.save(update_fields=['etude_params'])

    def _charge_utile(self):
        jeton = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=self.devis, token=jeton)
        reponse = DjangoClient().get(
            '/api/django/public/proposal/%s/data/' % jeton)
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    # ── 1. Sans simulation : rien ne change ──────────────────────────────────
    def test_sans_simulation_aucune_cle_bancable(self):
        charge = self._charge_utile()
        self.assertNotIn('bankable', charge)
        self.assertNotIn('bankable', charge['quote']['etude'])
        # Les clés historiques de l'étude sont toujours servies.
        self.assertEqual(charge['quote']['etude']['production_annuelle'],
                         12486)

    def test_sans_simulation_la_charge_utile_est_celle_d_hier(self):
        avant = self._charge_utile()
        apres = self._charge_utile()
        self.assertEqual(set(avant), set(apres))
        self.assertEqual(set(avant['quote']['etude']),
                         set(apres['quote']['etude']))

    # ── 2. Avec simulation : le titre à deux chiffres ────────────────────────
    def test_avec_simulation_le_titre_apparait(self):
        self._simuler()
        charge = self._charge_utile()
        self.assertIn('bankable', charge)
        titre = charge['bankable']
        self.assertEqual(set(titre),
                         {'p50_kwh', 'economies_25_ans', 'source'})
        self.assertEqual(titre['p50_kwh'], 71800)
        self.assertEqual(titre['source'], 'pvgis')
        self.assertIsNotNone(titre['economies_25_ans'])

    def test_l_economie_25_ans_est_celle_du_document(self):
        """Jamais un SECOND chiffre concurrent : c'est le cashflow du devis."""
        from apps.ventes.quote_engine.builder import build_quote_data

        self._simuler()
        data = build_quote_data(self.devis, {'pdf_mode': 'full'})
        attendu = (data['net_gain_avec'] if data.get('scenario') ==
                   'Avec batterie' else data['net_gain_sans'])
        charge = self._charge_utile()
        self.assertEqual(charge['bankable']['economies_25_ans'],
                         float(attendu))

    # ── 3. Aucune fuite d'interne ────────────────────────────────────────────
    def test_aucune_cle_interne_ne_fuit(self):
        self._simuler()
        charge = self._charge_utile()
        presentes = cles_profondes(charge)
        for interdite in CLES_INTERDITES:
            self.assertNotIn(interdite, presentes,
                             'clé interne servie au client : %s' % interdite)

    def test_aucune_valeur_interne_ne_fuit(self):
        self._simuler()
        brut = json.dumps(self._charge_utile(), ensure_ascii=False)
        for valeur in VALEURS_INTERDITES:
            self.assertNotIn(valeur, brut,
                             'valeur interne servie au client : %s' % valeur)

    def test_le_devis_garde_sa_simulation_intacte(self):
        """Lecture pure : la charge utile filtre, elle n'efface jamais rien."""
        self._simuler()
        statut = self.devis.statut
        self._charge_utile()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['simulation'], SIMULATION)
        self.assertEqual(self.devis.statut, statut)

    # ── Le filtre lui-même, unitairement ─────────────────────────────────────
    def test_le_filtre_ne_touche_pas_un_devis_sans_simulation(self):
        from apps.ventes.public_views import _sans_internes_bancables

        data = {'etude': {'production_annuelle': 1}, 'autre': 2}
        self.assertIs(_sans_internes_bancables(data), data)
        # Pas d'étude du tout → le dict revient tel quel, sans copie.
        sans_etude = {'autre': 2}
        self.assertIs(_sans_internes_bancables(sans_etude), sans_etude)

    def test_le_filtre_retire_les_deux_cles_bancables(self):
        from apps.ventes.public_views import _sans_internes_bancables

        data = {'etude': {'production_annuelle': 1, 'simulation': SIMULATION,
                          'bankable': SIMULATION}}
        propre = _sans_internes_bancables(data)
        self.assertEqual(propre['etude'], {'production_annuelle': 1})
        # L'original n'est jamais muté (le PDF vendeur lit le même dict).
        self.assertIn('simulation', data['etude'])

    def test_le_titre_est_none_sans_simulation(self):
        from apps.ventes.public_views import _bankable_headline

        self.assertIsNone(_bankable_headline(self.devis, {}))
