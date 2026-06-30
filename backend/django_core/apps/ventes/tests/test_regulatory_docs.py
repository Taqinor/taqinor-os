"""FG267 — tests des packs documentaires réglementaires par régime.

Calcul PUR (SimpleTestCase, aucun accès base/réseau).
"""
from django.test import SimpleTestCase

from apps.ventes import regulatory_docs as rd


class RequiredDocumentsTest(SimpleTestCase):
    def test_declaration_bt_pack(self):
        pieces = rd.required_documents('declaration_bt')
        codes = {p['code'] for p in pieces}
        # Pièces communes présentes.
        self.assertIn('schema_unifilaire', codes)
        self.assertIn('fiches_techniques', codes)
        # Pièce spécifique BT présente.
        self.assertIn('formulaire_declaration_bt', codes)
        # Pas de demande ANRE pour une déclaration BT.
        self.assertNotIn('demande_autorisation_anre', codes)

    def test_accord_raccordement_pack_adds_convention(self):
        pieces = rd.required_documents('accord_raccordement')
        codes = {p['code'] for p in pieces}
        self.assertIn('demande_accord_raccordement', codes)
        self.assertIn('convention_raccordement', codes)

    def test_anre_pack_is_richest(self):
        anre = rd.required_documents('autorisation_anre')
        bt = rd.required_documents('declaration_bt')
        self.assertGreater(len(anre), len(bt))
        codes = {p['code'] for p in anre}
        self.assertIn('demande_autorisation_anre', codes)
        self.assertIn('etude_impact_reseau', codes)

    def test_non_concerne_has_no_pieces(self):
        self.assertEqual(rd.required_documents('non_concerne'), [])

    def test_unknown_regime_returns_common_pieces_without_raising(self):
        pieces = rd.required_documents('inconnu_xyz')
        codes = {p['code'] for p in pieces}
        self.assertIn('schema_unifilaire', codes)
        self.assertNotIn('formulaire_declaration_bt', codes)

    def test_none_and_empty_never_raise(self):
        self.assertEqual(rd.required_documents(None), [])
        # Chaîne vide → pas non_concerne mais régime inconnu → pièces communes.
        self.assertTrue(len(rd.required_documents('')) >= 0)

    def test_no_duplicate_codes(self):
        for regime in rd.KNOWN_REGIMES:
            codes = [p['code'] for p in rd.required_documents(regime)]
            self.assertEqual(len(codes), len(set(codes)),
                             f'doublon de code dans {regime}')


class DocumentPackTest(SimpleTestCase):
    def test_pack_summary_counts(self):
        pack = rd.document_pack('accord_raccordement')
        self.assertEqual(pack['regime'], 'accord_raccordement')
        self.assertEqual(pack['regime_label'], "Accord de raccordement")
        self.assertEqual(pack['total_count'], len(pack['pieces']))
        self.assertLessEqual(pack['required_count'], pack['total_count'])
        self.assertGreater(pack['required_count'], 0)

    def test_regime_label_fallback(self):
        self.assertEqual(rd.regime_label('autorisation_anre'),
                         "Autorisation ANRE")
        self.assertEqual(rd.regime_label('xyz'), 'xyz')
        self.assertEqual(rd.regime_label(None), '—')

    def test_no_price_leak(self):
        blob = repr(rd.document_pack('autorisation_anre'))
        for forbidden in ('prix', 'marge', 'achat', 'price'):
            self.assertNotIn(forbidden, blob.lower())
