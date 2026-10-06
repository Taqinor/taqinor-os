"""AGR603 — régime hors réseau côté ventes (loi 82-21, art. 3).

Calcul PUR (SimpleTestCase) : l'autoconsommation isolée n'est PAS hors loi
82-21 ; elle relève d'une déclaration, quelle que soit la puissance.
"""
from django.test import SimpleTestCase

from apps.ventes import regulatory_docs as rd
from apps.ventes.connection_declaration import (
    build_declaration_data, render_declaration_html)
from apps.ventes.models_regulatory import REGIME_CHOICES


class RegimeHorsReseauTest(SimpleTestCase):
    def test_hors_reseau_sans_piece_ni_contrat_onee(self):
        pieces = rd.required_documents('declaration_hors_reseau')
        self.assertEqual(pieces, [])
        self.assertNotIn('contrat_onee', {p['code'] for p in pieces})

    def test_libelle(self):
        self.assertEqual(rd.regime_label('declaration_hors_reseau'),
                         "Déclaration hors réseau (loi 82-21, art. 3)")
        self.assertIn('declaration_hors_reseau', dict(REGIME_CHOICES))

    def test_pack_expose_le_motif(self):
        pack = rd.document_pack('declaration_hors_reseau')
        self.assertEqual(pack['pieces'], [])
        self.assertEqual(pack['total_count'], 0)
        self.assertIn('décret 2.25.100', pack['motif_pieces'])

    def test_regimes_historiques_inchanges(self):
        # Sortie octet-identique : jamais de clé motif pour les 4 historiques.
        for regime in ('non_concerne', 'declaration_bt',
                       'accord_raccordement', 'autorisation_anre'):
            pack = rd.document_pack(regime)
            self.assertEqual(
                set(pack), {'regime', 'regime_label', 'pieces',
                            'required_count', 'total_count'})
        self.assertIn('contrat_onee', {
            p['code'] for p in rd.required_documents('declaration_bt')})
        self.assertEqual(rd.regime_label('non_concerne'),
                         "Non concerné (hors loi 82-21)")

    def test_devis_agricole_hors_reseau_15_kwc(self):
        regime = rd.regime_8221_pour_devis('agricole', 'hors_reseau')
        self.assertEqual(regime, 'declaration_hors_reseau')
        self.assertNotIn(regime, ('accord_raccordement', 'non_concerne'))

    def test_devis_raccorde_pas_de_suggestion_locale(self):
        self.assertIsNone(rd.regime_8221_pour_devis('agricole', 'raccorde'))
        self.assertIsNone(rd.regime_8221_pour_devis('residentiel', ''))


class _Devis:
    reference = 'DEV-AGR603'
    client = None
    etude_params = {'puissance_kwc': 15}


class DeclarationHorsReseauTest(SimpleTestCase):
    def test_declaration_hors_reseau_affiche_motif(self):
        data = build_declaration_data(
            _Devis(), diagram_params={'n_panneaux': 30,
                                      'puissance_panneau_wc': 500},
            regime_8221='declaration_hors_reseau')
        self.assertEqual(data['systeme']['kwc'], 15.0)
        self.assertEqual(data['raccordement'], 'hors réseau')
        self.assertEqual(data['pieces'], [])
        self.assertIn('décret 2.25.100', data['motif_pieces'])
        html = render_declaration_html(data)
        self.assertIn('décret 2.25.100', html)
        self.assertNotIn('ONEE du point de livraison', html)

    def test_declaration_bt_inchangee(self):
        data = build_declaration_data(
            _Devis(), diagram_params={'n_panneaux': 10,
                                      'puissance_panneau_wc': 500},
            regime_8221='declaration_bt')
        # CIQ615 — sans niveau mesuré ni déclaré : champ vide (jamais déduit
        # des phases), pièce « niveau à relever » listée.
        self.assertEqual(data['raccordement'], '')
        self.assertIn('niveau_tension_a_relever',
                      {p['code'] for p in data['pieces']})
        self.assertNotIn('motif_pieces', data)
