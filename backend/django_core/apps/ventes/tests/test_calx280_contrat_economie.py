"""CALX280 — le CONTRAT du bloc économie servi par ``apps/ventes``.

PACT10 : le contrat part SEUL et EN PREMIER. Ce test ne retape aucune forme :
il LIT le document partagé ``apps/ventes/contract_samples/ventes_economie.json``
(le même que les deux moitiés — ``economie.py``/la vue CALX288 côté serveur,
l'onglet « Économie » CALX289 côté atelier — importeront) et affirme ses
invariants.

Ce qui est prouvé (le « Done » de CALX280) :

* le document porte ``endpoint``/``exemple`` au format de la garde
  ``scripts/check_api_shapes.py`` et l'endpoint est celui du plan ;
* ``exemple`` et ``exemple_vide`` portent EXACTEMENT les clés du contrat — un
  autre ÉTAT du serveur, jamais une autre FORME ;
* l'exemple committé porte AU MOINS une entrée d'``omissions`` ;
* chaque ``hypotheses[].source`` est non vide ;
* aucune grandeur n'est à la fois une hypothèse et une omission (une grandeur
  non saisie n'apparaît jamais dans ``hypotheses`` avec un défaut) ;
* la garde de vocabulaire de ``apps/calepinage/services/note_calcul.py``
  (``CLES_INTERDITES``) ne trouve AUCUNE clé interdite dans l'exemple, et
  aucune clé ne contient ``prix``, ``cout`` ni ``marge``.

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python -m pytest apps/ventes/tests/test_calx280_contrat_economie.py -q
"""
import json
import unittest
from pathlib import Path

from apps.calepinage.services import note_calcul

#: Le document PARTAGÉ (PACT10) — jamais une charge utile retapée ici.
CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'ventes_economie.json')

#: Les clés du bloc, telles que l'énoncé de CALX280 les liste.
CLES_BLOC = {
    'horizon_ans', 'flux', 'van_mad', 'tri_pct', 'lcoe_mad_kwh',
    'retour_ans', 'retour_actualise_ans', 'hypotheses', 'omissions',
}
CLES_FLUX = {'annee', 'economie_mad', 'flux_mad', 'cumul_mad',
             'flux_actualise_mad'}
CLES_HYPOTHESE = {'cle', 'valeur', 'source', 'saisie_le'}
CLES_OMISSION = {'cle', 'motif'}

#: Sous-chaînes interdites dans un NOM de clé (énoncé CALX280/CALX288).
MOTS_INTERDITS = ('prix', 'cout', 'marge')

VARIANTES = ('exemple', 'exemple_vide')


def document():
    return json.loads(CONTRAT.read_text(encoding='utf-8'))


def toutes_les_cles(noeud):
    """Chaque NOM de clé d'une structure JSON imbriquée, à plat."""
    trouvees = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            trouvees.append(str(cle))
            trouvees.extend(toutes_les_cles(valeur))
    elif isinstance(noeud, list):
        for valeur in noeud:
            trouvees.extend(toutes_les_cles(valeur))
    return trouvees


class ContratEconomieTest(unittest.TestCase):
    def test_endpoint_et_format_de_la_garde(self):
        doc = document()
        self.assertEqual(
            doc['endpoint'], 'GET /api/django/ventes/devis/<int:pk>/economie/')
        self.assertTrue(doc['pourquoi'].strip())
        self.assertIsInstance(doc['exemple'], dict)

    def test_chaque_variante_porte_exactement_les_cles_du_contrat(self):
        doc = document()
        for variante in VARIANTES:
            with self.subTest(variante=variante):
                bloc = doc[variante]
                self.assertEqual(set(bloc), CLES_BLOC)
                self.assertIsInstance(bloc['flux'], list)
                for ligne in bloc['flux']:
                    self.assertEqual(set(ligne), CLES_FLUX)
                for hypothese in bloc['hypotheses']:
                    self.assertEqual(set(hypothese), CLES_HYPOTHESE)
                for omission in bloc['omissions']:
                    self.assertEqual(set(omission), CLES_OMISSION)

    def test_l_exemple_porte_au_moins_une_omission_motivee(self):
        omissions = document()['exemple']['omissions']
        self.assertGreaterEqual(len(omissions), 1)
        for omission in omissions:
            self.assertTrue(str(omission['cle']).strip())
            self.assertTrue(str(omission['motif']).strip())

    def test_chaque_hypothese_porte_une_source_non_vide(self):
        doc = document()
        for variante in VARIANTES:
            for hypothese in doc[variante]['hypotheses']:
                with self.subTest(variante=variante, cle=hypothese['cle']):
                    self.assertIsInstance(hypothese['source'], str)
                    self.assertTrue(hypothese['source'].strip())

    def test_une_grandeur_omise_n_est_jamais_une_hypothese(self):
        doc = document()
        for variante in VARIANTES:
            bloc = doc[variante]
            saisies = {h['cle'] for h in bloc['hypotheses']}
            omises = {o['cle'] for o in bloc['omissions']}
            with self.subTest(variante=variante):
                self.assertEqual(saisies & omises, set())

    def test_un_indicateur_nul_est_toujours_motive(self):
        """``null`` n'est jamais muet : chaque indicateur non publié a son
        entrée dans ``omissions``."""
        indicateurs = ('van_mad', 'tri_pct', 'lcoe_mad_kwh', 'retour_ans',
                       'retour_actualise_ans')
        doc = document()
        for variante in VARIANTES:
            bloc = doc[variante]
            omises = {o['cle'] for o in bloc['omissions']}
            for cle in indicateurs:
                if bloc[cle] is None:
                    with self.subTest(variante=variante, cle=cle):
                        self.assertIn(cle, omises)

    def test_le_cas_de_reference_est_coherent(self):
        """L'exemple reprend le cas de référence de CALX281/CALX282 : le
        cumul de chaque ligne est la somme des flux, le retour est la
        première année où il devient positif ou nul, la VAN à taux nul est
        la somme des flux."""
        bloc = document()['exemple']
        cumul = 0.0
        premiere = None
        for ligne in bloc['flux']:
            cumul += ligne['flux_mad']
            self.assertAlmostEqual(ligne['cumul_mad'], cumul, places=2)
            if premiere is None and cumul >= 0:
                premiere = ligne['annee']
        self.assertEqual(bloc['retour_ans'], premiere)
        self.assertEqual(len(bloc['flux']), bloc['horizon_ans'] + 1)
        self.assertAlmostEqual(
            bloc['van_mad'],
            sum(ligne['flux_actualise_mad'] for ligne in bloc['flux']),
            places=2)

    def test_la_garde_de_vocabulaire_ne_trouve_aucune_cle_interdite(self):
        doc = document()
        for variante in VARIANTES:
            bloc = doc[variante]
            with self.subTest(variante=variante):
                # La garde elle-même : elle LÈVE sur une clé de coût.
                note_calcul._verifier_etancheite(bloc)
                for cle in toutes_les_cles(bloc):
                    self.assertFalse(note_calcul._cle_interdite(cle), cle)
                    for mot in MOTS_INTERDITS:
                        self.assertNotIn(mot, cle.lower(), cle)

    def test_la_garde_de_vocabulaire_rougit_vraiment(self):
        """Preuve que l'assertion ci-dessus peut échouer : la même garde
        refuse une clé ``prix`` posée volontairement."""
        with self.assertRaises(note_calcul.NoteRefusee):
            note_calcul._verifier_etancheite({'flux': [{'prix': 1.0}]})


if __name__ == '__main__':
    unittest.main()
