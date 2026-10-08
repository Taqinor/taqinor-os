"""AMOT42 (C-AMOT-053) — ``echapper_textes_client`` parcourt ``economie_ci`` :
les textes saisis (prêteur, référence d'offre) recomposés en libellé sont
échappés UNE fois avant rendu ; le HTML porte « Banque &lt;X &amp; Co (réf.
R1) », jamais un « < » brut qui mange la suite, ni un double échappement.

Fonction réelle ; libellé réel de ``economie_ci._libelle_financement``.

Test-du-test : retirer ``economie_ci`` du parcours ⇒
``test_libelle_financement_echappe`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.economie_ci import _libelle_financement
from apps.ventes.quote_engine.builder import echapper_textes_client


class EchappementEconomieCiTests(SimpleTestCase):

    def _data(self):
        libelle = _libelle_financement(
            {'preteur': 'Banque <X & Co', 'reference_offre': 'R1'},
            'credit', False)
        return {'economie_ci': {
            'financement': {'libelle_client': libelle, 'duree_mois': 84,
                            'echeance_mad': 1234.5},
            'tarif': {'contrat': 'bt_patente'},
            'mentions': ['Texte <libre>'],
        }}

    def test_libelle_financement_echappe(self):
        sortie = echapper_textes_client(self._data())
        libelle = sortie['economie_ci']['financement']['libelle_client']
        self.assertIn('Banque &lt;X &amp; Co', libelle)
        self.assertIn('(réf. R1)', libelle)
        self.assertNotIn('&amp;lt;', libelle)

    def test_nombres_et_cles_intacts(self):
        sortie = echapper_textes_client(self._data())
        fin = sortie['economie_ci']['financement']
        self.assertEqual(fin['duree_mois'], 84)
        self.assertEqual(fin['echeance_mad'], 1234.5)
        self.assertEqual(sortie['economie_ci']['tarif']['contrat'],
                         'bt_patente')
        self.assertEqual(sortie['economie_ci']['mentions'],
                         ['Texte &lt;libre&gt;'])

    def test_source_non_modifiee(self):
        data = self._data()
        echapper_textes_client(data)
        self.assertIn('<X', data['economie_ci']['financement']['libelle_client'])
