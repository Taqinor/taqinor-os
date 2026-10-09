"""AMOT31 (C-AMOT-032) — le moteur de dimensionnement ne compte que les lignes
VENDUES (``domain.dimensionnement_devis.lignes_vendues`` =
``compte_dans_totaux`` + variante) : une ligne OPTIONNELLE ne change aucune
capacité, calibre, matériel, module ni facteur de remise, et « Appliquer » ne
l'écrit jamais.

Lignes ORM réelles, lecteurs réels, aucun mock. Test-du-test : retirer le
filtre ``compte_dans_totaux`` de ``lignes_vendues`` ⇒
``test_lecteurs_identiques_sans_option`` échoue (capacité 5,0).
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes import offres_tailles as ot
from apps.ventes.dimensionnement import config_vendue_du_devis
from apps.ventes.domain.dimensionnement_devis import (
    capacite_batterie_des_lignes, facteur_remise_du_devis, lignes_vendues,
    module_batterie_du_devis,
)
from apps.ventes.models import LigneDevis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_produit, make_user,
)

_LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
]


class LignesVenduesTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot31-co', nom='AMOT31')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                _LIGNES, remise_globale='5',
                                reference='DEV-AMOT31-1')
        self.temoin = make_devis(self.company, self.user, self.client_obj,
                                 _LIGNES, remise_globale='5',
                                 reference='DEV-AMOT31-2')
        produit = make_produit(self.company, 'Batterie Dyness 5 kWh',
                               'AMOT31-BAT', '20000')
        self.option = LigneDevis.objects.create(
            devis=self.devis, produit=produit,
            designation='Batterie Dyness 5 kWh', quantite=Decimal('1'),
            prix_unitaire=Decimal('20000'), remise=Decimal('0'),
            optionnelle=True)

    def _sorties(self, devis):
        return {
            'capacite': capacite_batterie_des_lignes(devis),
            'module': module_batterie_du_devis(devis),
            'facteur': round(facteur_remise_du_devis(devis), 6),
            'modules': ot._compter_modules_du_devis(devis),
            'materiel_avec': [e.get('famille') for e in
                              ot._materiel_du_devis(devis, 'avec')[0]],
            'config_batterie': getattr(config_vendue_du_devis(devis),
                                       'batterie_kwh', None),
        }

    def test_lecteurs_identiques_sans_option(self):
        self.assertNotIn(self.option.pk,
                         [li.pk for li in lignes_vendues(self.devis)])
        self.assertEqual(self._sorties(self.devis), self._sorties(self.temoin))
        self.assertIsNone(capacite_batterie_des_lignes(self.devis))
        self.assertEqual(ot._compter_modules_du_devis(self.devis), 0)
        # Le TTC du devis (noyau) ignore l'option, comme les lecteurs.
        self.assertEqual(self.devis.total_ttc, self.temoin.total_ttc)

    def test_appliquer_ne_touche_pas_la_ligne_optionnelle(self):
        self.assertIsNone(ot._porter_modules_batterie(self.devis, 3))
        # CLAUSE PERSISTANCE — relire : la ligne optionnelle est inchangée.
        self.option.refresh_from_db()
        self.assertEqual(self.option.quantite, Decimal('1'))
        self.assertTrue(self.option.optionnelle)

    def test_variante(self):
        self.devis.lignes.filter(designation='Panneau mono 550W').update(
            variante='sans')
        self.assertEqual(
            [li.designation for li in lignes_vendues(self.devis, 'avec')],
            ['Onduleur réseau Huawei 5kW'])
