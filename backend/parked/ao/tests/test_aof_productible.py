"""AOF113 — un seul productible pour la note de calcul et la simulation.

    python -m unittest apps.ao.tests.test_aof_productible -v
"""
import ast
import pathlib
import unittest

from apps.ao.fabrique import productible as prod
from apps.ao.fabrique.contexte import construire_contexte, valeur

RACINE = pathlib.Path(__file__).resolve().parents[3]
FABRIQUE = pathlib.Path(__file__).resolve().parents[1] / 'fabrique'


def table_canonique():
    """Relit la table canonique INDÉPENDAMMENT du module testé."""
    source = (RACINE / prod.CHEMIN_TABLE).read_text(encoding='utf-8')
    for noeud in ast.parse(source).body:
        if isinstance(noeud, ast.Assign) and any(
                isinstance(c, ast.Name) and c.id == 'PRODUCTIBLE_PAR_VILLE'
                for c in noeud.targets):
            return ast.literal_eval(noeud.value)
    raise AssertionError('PRODUCTIBLE_PAR_VILLE introuvable')


class TestSourceUnique(unittest.TestCase):

    def test_la_table_lue_est_la_table_committee(self):
        """Le seul garde-fou qui rend la divergence impossible."""
        attendue = {str(k).lower(): float(v)
                    for k, v in table_canonique().items()}
        self.assertEqual(prod.table(), attendue)
        self.assertTrue(attendue, 'table canonique vide')

    def test_villes_reelles(self):
        self.assertEqual(prod.resoudre('Casablanca')['valeur_kwh_kwc'],
                         prod.table()['casablanca'])
        self.assertEqual(prod.resoudre('agadir')['valeur_kwh_kwc'],
                         prod.table()['agadir'])

    def test_alias_resolus_comme_dans_la_table_canonique(self):
        r = prod.resoudre('Mohammedia')
        self.assertEqual(r['ville_retenue'], 'casablanca')
        self.assertIn('alias', r['methode'])

    def test_ville_inconnue_replie_sans_inventer(self):
        r = prod.resoudre('Tombouctou')
        self.assertIn('repli', r['methode'])
        self.assertGreater(r['valeur_kwh_kwc'], 0)

    def test_override_societe_prime_sauf_valeur_d_usine(self):
        self.assertEqual(
            prod.resoudre('Casablanca', override=1720)['valeur_kwh_kwc'], 1720.0)
        # 1600 = défaut d'usine : ce n'est PAS un choix de l'opérateur.
        self.assertEqual(
            prod.resoudre('Casablanca', override=1600)['valeur_kwh_kwc'],
            prod.table()['casablanca'])

    def test_resolution_deterministe(self):
        self.assertEqual(prod.resoudre('Rabat'), prod.resoudre('Rabat'))

    def test_revision_stable_et_courte(self):
        self.assertEqual(len(prod.revision()), 12)
        self.assertEqual(prod.revision(), prod.resoudre('Rabat')['revision'])


class TestPieceCiteSaSource(unittest.TestCase):

    def test_phrase_source_porte_valeur_source_et_revision(self):
        phrase = prod.phrase_source(prod.resoudre('Casablanca'))
        self.assertIn('kWh/kWc/an', phrase)
        self.assertIn(prod.CHEMIN_TABLE, phrase)
        self.assertIn(prod.revision(), phrase)
        self.assertIn('PVGIS', phrase)

    def test_date_de_verification_citee_quand_connue(self):
        phrase = prod.phrase_source(
            prod.resoudre('Casablanca', date_verification='2026-08-01'))
        self.assertIn('2026-08-01', phrase)


class TestUneSeuleValeurDansLeDossier(unittest.TestCase):

    def contexte(self):
        resolution = prod.resoudre('Casablanca')
        return construire_contexte(
            {'identite': {'raison_sociale': 'TAQINOR SARL'},
             'marche': {'objet': 'centrale PV'},
             'montants': {'total_ht': '1', 'total_ttc': '1.2'}},
            productible=resolution)

    def test_note_de_calcul_et_simulation_lisent_la_meme_valeur(self):
        c = self.contexte()
        note = valeur(c, 'productible.valeur_kwh_kwc')
        simulation = valeur(c, 'productible.valeur_kwh_kwc')
        self.assertEqual(note, simulation)
        self.assertEqual(note, prod.table()['casablanca'])

    def test_la_production_annuelle_derive_de_cette_valeur_seule(self):
        c = self.contexte()
        kwh = prod.production_annuelle_kwh(c['productible'], 350.0)
        self.assertAlmostEqual(kwh, prod.table()['casablanca'] * 350.0, places=6)

    def test_le_contexte_ne_porte_qu_un_seul_productible(self):
        c = self.contexte()
        from apps.ao.fabrique.contexte import cles_disponibles
        chemins = [ch for ch in cles_disponibles(c)
                   if ch.endswith('valeur_kwh_kwc')
                   or ch.endswith('productible_kwh_kwc')]
        self.assertEqual(chemins, ['productible.valeur_kwh_kwc'])

    def test_le_contexte_marque_l_absence_d_appel_reseau(self):
        self.assertIs(self.contexte()['productible']['reseau'], False)


class TestAucunReseauNiCouplageAuMoteurDeDevis(unittest.TestCase):

    def modules(self):
        return sorted(FABRIQUE.rglob('*.py'))

    def test_aucun_import_reseau_dans_la_fabrique(self):
        interdits = {'requests', 'urllib', 'http', 'socket', 'httpx',
                     'urllib3'}
        fautes = []
        for fichier in self.modules():
            arbre = ast.parse(fichier.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                noms = []
                if isinstance(noeud, ast.Import):
                    noms = [a.name for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    noms = [noeud.module or '']
                for nom in noms:
                    if nom.split('.')[0] in interdits:
                        fautes.append('%s:%d %s' % (fichier.name,
                                                    noeud.lineno, nom))
        self.assertEqual(fautes, [], '\n'.join(fautes))

    def test_aucun_import_de_quote_engine_dans_la_fabrique(self):
        """Règle #4 : la fabrique AO est un domaine séparé, pas même en lecture."""
        fautes = []
        for fichier in self.modules():
            texte = fichier.read_text(encoding='utf-8')
            for numero, ligne in enumerate(texte.splitlines(), 1):
                nue = ligne.strip()
                if not (nue.startswith('import ') or nue.startswith('from ')):
                    continue
                if 'quote_engine' in nue or 'apps.ventes' in nue:
                    fautes.append('%s:%d %s' % (fichier.name, numero, nue))
        self.assertEqual(fautes, [], '\n'.join(fautes))


if __name__ == '__main__':
    unittest.main()
