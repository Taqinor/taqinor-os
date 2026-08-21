"""GAMMES — 6. Garanties du PDF dérivées de la composition.

Partie 6 sur 8 de l'ancien `test_gammes_offre.py`, scindé PAR CLASSE le
2026-08-21 (voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

Décision fondateur 2026-08-18 couverte ici : les garanties du PDF dérivent de
la composition réelle (repli constante).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_garanties -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import Produit
from apps.ventes.tests._gammes_offre_common import (
    add_ligne, make_client_obj, make_company, make_devis, make_user,
)


class TestGarantiesDerivees(TestCase):
    """La bande « Nos garanties » lit les durées CATALOGUE des produits du
    devis rendu ; sans donnée produit, la constante d'aujourd'hui ; sans
    composant reconnu ni constante, OMISSION (jamais un chiffre inventé)."""

    def _labels(self, rows):
        from apps.ventes.quote_engine.residential import theme
        return {label: n for n, _u, label, _sub in
                theme.warranties_for({'sans_items': rows})}

    def test_sans_donnee_produit_la_garantie_est_omise(self):
        """M6 (audit adversarial du 19/08/2026) — LE REPLI-CONSTANTE EST MORT.

        Un produit dont AUCUNE garantie n'est saisie n'a pas de garantie
        connue : le document l'OMET au lieu de recopier une durée de
        catalogue. Seules deux entrées survivent sans donnée produit, et
        chacune pour une raison nommée :

        * « Installation » — 2 ans de main-d'œuvre, l'engagement de
          l'ENTREPRISE, pas une spec produit : inconditionnel ;
        * le panneau par défaut du catalogue (Canadian Solar), dont les
          durées SONT ses valeurs constructeur — une dérivation traçable.

        Tout le reste tombe : l'onduleur Huawei, sans garantie saisie, n'a
        plus sa ligne « 10 ans » sortie d'un dictionnaire.
        """
        rows = [
            {'designation': 'Panneau Canadian Solar 710W'},
            {'designation': 'Onduleur réseau Huawei 5kW'},
        ]
        labels = self._labels(rows)
        self.assertNotIn('Onduleur', labels)
        self.assertEqual(labels['Installation'], '2')

    def test_sans_donnee_produit_un_autre_panneau_est_omis_aussi(self):
        """Le repli du panneau par défaut ne déteint pas sur les autres : un
        Longi sans garantie saisie n'emprunte pas les durées — ni surtout le
        « 87,4 % » — d'un Canadian Solar."""
        from apps.ventes.quote_engine.residential import theme
        rows = [
            {'designation': 'Panneau Longi 585W'},
            {'designation': 'Onduleur réseau Deye 5kW'},
        ]
        self.assertEqual(theme.warranties_for({'sans_items': rows}),
                         [theme._WARRANTY_FALLBACK['Installation']])

    def test_durees_produit_prises_en_compte(self):
        labels = self._labels([
            {'designation': 'Panneau Trina 600W', 'garantie_mois': 300,
             'garantie_production_mois': 360},
            {'designation': 'Onduleur réseau Deye 5kW', 'garantie_mois': 144},
        ])
        self.assertEqual(labels['Panneaux'], '25')
        self.assertEqual(labels['Performance'], '30')
        self.assertEqual(labels['Onduleur'], '12')
        self.assertEqual(labels['Installation'], '2')

    def test_composant_absent_est_omis(self):
        labels = self._labels([{'designation': 'Pompe solaire OSP 30-12'}])
        self.assertNotIn('Panneaux', labels)
        self.assertNotIn('Onduleur', labels)
        self.assertIn('Installation', labels)

    def test_batterie_sans_duree_produit_est_omise(self):
        labels = self._labels([
            {'designation': 'Panneau Trina 600W'},
            {'designation': 'Batterie Lithium 5 kWh'},
        ])
        self.assertNotIn('Batterie', labels)

    def test_batterie_avec_duree_produit_apparait(self):
        labels = self._labels([
            {'designation': 'Batterie Lithium 5 kWh', 'garantie_mois': 120},
        ])
        self.assertEqual(labels['Batterie'], '10')

    def test_performance_derivee_ne_reprend_pas_le_sous_libelle_chiffre(self):
        from apps.ventes.quote_engine.residential import theme
        rows = [{'designation': 'Panneau Trina 600W',
                 'garantie_production_mois': 300}]
        subs = {label: sub for _n, _u, label, sub in
                theme.warranties_for({'sans_items': rows})}
        self.assertEqual(subs['Performance'], 'performance linéaire')

    def test_ligne_de_devis_porte_les_durees_catalogue(self):
        """``builder._line_to_item`` injecte les durées structurées (elles
        alimentent la dérivation ci-dessus)."""
        from apps.ventes.quote_engine.builder import _line_to_item
        company = make_company('gamme-gar')
        user = make_user(company, 'u_gamme_gar')
        client_obj = make_client_obj(company)
        produit = Produit.objects.create(
            company=company, nom='Panneau Trina 600W', sku='PAN-GAR',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            quantite_stock=10, garantie_mois=300,
            garantie_production_mois=360)
        devis = make_devis(company, user, client_obj, 'DEV-GAM-060')
        ligne = add_ligne(devis, produit, qty='10')
        item = _line_to_item(ligne, Decimal('20'))
        self.assertEqual(item['garantie_mois'], 300)
        self.assertEqual(item['garantie_production_mois'], 360)
