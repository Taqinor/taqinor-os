"""AGR305 — garanties par composant d'un devis de pompage (pompe, variateur,
panneaux), dérivées des fiches des lignes — jamais la constante résidentielle
``theme.WARRANTIES``. Tests PURS (aucune base, aucun rendu)."""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole.garanties import (
    garanties_pompage, garanties_pompage_et_omissions,
)
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole


def _pompe(**kw):
    it = {'designation': 'Pompe immergée OSP 30/8', 'role_pompage': 'pompe',
          'garantie': '24', 'garantie_mois': None,
          'garantie_production_mois': None}
    it.update(kw)
    return it


def _variateur(**kw):
    it = {'designation': 'VARIATEUR VEICHI SI23 7.5KW 380V',
          'role_pompage': 'variateur_pompage',
          'garantie': 'constructeur 2 ans', 'garantie_mois': None,
          'garantie_production_mois': None}
    it.update(kw)
    return it


def _panneau(**kw):
    it = {'designation': 'Panneau mono 710W', 'role_pompage': None,
          'role_devis': 'panneau', 'garantie_mois': None,
          'garantie_production_mois': None}
    it.update(kw)
    return it


class Agr305GarantiesTests(SimpleTestCase):

    def test_pompe_a_24_mois_rend_2_ans(self):
        g = garanties_pompage([_pompe(garantie_mois=24)])
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]['composant'], 'pompe')
        self.assertEqual(g[0]['mois'], 24)
        self.assertIn('2 ans', g[0]['libelle'])

    def test_variateur_sans_duree_structuree_est_omis_avec_motif(self):
        """Le texte « constructeur 2 ans » n'est JAMAIS interprété."""
        g, omissions = garanties_pompage_et_omissions([_variateur()])
        self.assertEqual(g, [])
        self.assertIn({'bloc': 'garanties.variateur',
                       'motif': 'garantie non renseignée'}, omissions)

    def test_le_texte_24_d_une_pompe_n_est_jamais_lu(self):
        g, omissions = garanties_pompage_et_omissions([_pompe()])
        self.assertEqual(g, [])
        self.assertIn('garanties.pompe', {o['bloc'] for o in omissions})

    def test_panneaux_produit_et_production(self):
        g = garanties_pompage([_panneau(garantie_mois=144,
                                        garantie_production_mois=360)])
        self.assertEqual(
            [(x['composant'], x['mois']) for x in g],
            [('panneaux', 144), ('performance_panneaux', 360)])
        self.assertIn('12 ans', g[0]['libelle'])
        self.assertIn('30 ans', g[1]['libelle'])

    def test_aucune_duree_de_theme_warranties_pour_un_devis_pompage(self):
        from apps.ventes.quote_engine.residential.theme import WARRANTIES
        items = [_pompe(garantie_mois=24), _variateur(), _panneau()]
        g, omissions = garanties_pompage_et_omissions(items)
        libelles = ' '.join(x['libelle'] for x in g)
        for nombre, unite, label, sous in WARRANTIES:
            with self.subTest(label=label):
                self.assertNotIn(label, [x['composant'] for x in g])
                self.assertNotIn(sous, libelles)
        # Aucune ligne « Installation » / « Onduleur » résidentielle.
        self.assertEqual({x['composant'] for x in g}, {'pompe'})
        # La pose est omise tant que le fondateur ne l'a pas décidée.
        self.assertIn('garanties.installation',
                      {o['bloc'] for o in omissions})

    def test_composition_vide_liste_vide_jamais_le_repli(self):
        self.assertEqual(garanties_pompage([]), [])
        self.assertEqual(garanties_pompage(None), [])
        self.assertEqual(garanties_pompage_et_omissions([]), ([], []))

    def test_sans_role_pompage_pompe_et_variateur_ne_sont_pas_devines(self):
        items = [_pompe(role_pompage=None, garantie_mois=24),
                 _variateur(role_pompage=None, garantie_mois=24)]
        self.assertEqual(garanties_pompage(items), [])

    def test_ordre_pompe_variateur_panneaux(self):
        items = [_panneau(garantie_mois=120), _variateur(garantie_mois=24),
                 _pompe(garantie_mois=12)]
        g = garanties_pompage(items)
        self.assertEqual([x['composant'] for x in g],
                         ['pompe', 'variateur', 'panneaux'])
        self.assertIn('1 an', g[0]['libelle'])
        self.assertNotIn('1 ans', g[0]['libelle'])

    def test_la_synthese_porte_les_garanties(self):
        data = {'etude': {}, 'all_items': [_pompe(garantie_mois=24),
                                           _variateur()]}
        s = synthese_agricole(data)
        self.assertEqual([x['composant'] for x in s['garanties']], ['pompe'])
        self.assertIn('garanties.variateur',
                      {o['bloc'] for o in s['omissions']})
