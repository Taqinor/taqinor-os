"""Tests AUD515 -- scripts/check_machine_etats_statut_readonly.py.

Pur stdlib (unittest), sans Django ni base -- comme le garde lui-meme.
Lancer :
    python -m unittest scripts.tests.test_check_machine_etats_statut_readonly -v

Ce que ces tests verrouillent :
  * le detecteur VOIT (un garde vert sans cette preuve ne dit rien) -- il
    liste bien les divergences reelles du depot en mode `--tout` ;
  * les quatre formes de « porte fermee » sont acceptees, et elles seules ;
  * la decouverte est SEMANTIQUE : elle vient d'un `machine_etats.py` ou d'une
    fonction `changer_statut*`, jamais d'une liste ecrite a la main ;
  * la base de reprise ne peut porter que des cles reellement observees --
    une entree morte serait une PRE-AUTORISATION silencieuse.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_machine_etats_statut_readonly as garde  # noqa: E402


def _classe(source: str) -> ast.ClassDef:
    """La premiere classe du source fourni."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            return node
    raise AssertionError('aucune classe dans le source de test')


OUVERT = '''\
class ContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        fields = '__all__'
        read_only_fields = ['reference']
'''

READ_ONLY = '''\
class ContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        fields = '__all__'
        read_only_fields = ['reference', 'statut']
'''

VALIDATE = '''\
class ContratSerializer(serializers.ModelSerializer):
    def validate_statut(self, value):
        return value

    class Meta:
        model = Contrat
        fields = '__all__'
'''

FIELDS_SANS_STATUT = '''\
class ContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        fields = ['id', 'reference']
'''

EXCLUDE_STATUT = '''\
class ContratSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contrat
        exclude = ['statut']
'''


class LesQuatreFormesDePorteFermee(unittest.TestCase):
    def test_statut_writable_est_une_porte_ouverte(self):
        self.assertFalse(garde.porte_fermee(_classe(OUVERT)))

    def test_read_only_fields(self):
        self.assertTrue(garde.porte_fermee(_classe(READ_ONLY)))

    def test_validate_statut(self):
        self.assertTrue(garde.porte_fermee(_classe(VALIDATE)))

    def test_fields_explicite_sans_statut(self):
        self.assertTrue(garde.porte_fermee(_classe(FIELDS_SANS_STATUT)))

    def test_exclude_statut(self):
        self.assertTrue(garde.porte_fermee(_classe(EXCLUDE_STATUT)))


class LaDecouverteEstSemantique(unittest.TestCase):
    """Aucune liste statique : les modeles gouvernes viennent du CODE."""

    def test_le_depot_declare_bien_des_modeles_gouvernes(self):
        gouvernes = garde.inventaire()
        self.assertTrue(gouvernes)
        # Les deux modules `machine_etats.py` du depot, au minimum.
        self.assertIn('contrats.Contrat', gouvernes)
        self.assertIn('sav.Ticket', gouvernes)

    def test_une_fonction_changer_statut_gouverne_son_premier_parametre(self):
        """`changer_statut_vehicule(vehicule, ...)` -> `Vehicule`."""
        self.assertIn('flotte.Vehicule', garde.inventaire())


class LeDetecteurVoit(unittest.TestCase):
    """Preuve ROUGE : sans elle, un garde vert ne dit rien (lecon OR3)."""

    def test_les_divergences_reelles_sont_listees_en_mode_tout(self):
        """Le mode `--tout` doit voir l'existant que la base de reprise gele.

        On n'EPINGLE aucun modele : la liste DECROIT au fil des taches (AUD501
        en a retire `contrats.Contrat` le jour meme). Ce qui doit rester vrai,
        c'est que chaque entree GELEE est effectivement OBSERVEE -- sinon le
        garde ne verrait rien et sa base pre-autoriserait dans le vide."""
        brutes = garde.divergences(inclure_reprise=True)
        self.assertTrue(
            brutes,
            'le garde ne voit AUCUNE divergence : il ne protege rien')
        observees = {ligne.split()[1] for ligne in brutes}
        self.assertTrue(set(garde.base_de_reprise()) <= observees)

    def test_la_base_de_reprise_tait_l_existant(self):
        """En mode CI, les entrees figees ne rougissent pas."""
        self.assertEqual(garde.divergences(), [])


class LaBaseDeRepriseEstVIVANTE(unittest.TestCase):
    def test_chaque_entree_porte_une_raison(self):
        entrees = garde.base_de_reprise()
        self.assertTrue(entrees, 'la base de reprise est vide')
        sans_raison = [k for k, raison in entrees.items() if not raison]
        self.assertEqual(sans_raison, [])

    def test_aucune_entree_morte(self):
        """Une entree qui ne correspond plus a aucune divergence PRE-AUTORISE
        en silence une reintroduction : elle doit etre retiree."""
        observees = set()
        for ligne in garde.divergences(inclure_reprise=True):
            # « chemin:ligne  app.Modele.Serialiseur -- ... »
            observees.add(ligne.split()[1])
        mortes = sorted(set(garde.base_de_reprise()) - observees)
        self.assertEqual(
            mortes, [],
            f'entree(s) morte(s) dans {garde.ALLOWLIST_PATH.name} : {mortes}')


if __name__ == '__main__':
    unittest.main()
