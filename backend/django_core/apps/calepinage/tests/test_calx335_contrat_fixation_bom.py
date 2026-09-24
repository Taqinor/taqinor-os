"""CALX335 — le contrat de la nomenclature de fixation, affirmé sans base.

Ce qui est prouvé ici, sur l'échantillon committé
``contract_samples/calepinage_fixation_bom.json`` :

* l'endpoint est celui que CALX359 servira (``GET …/bom-fixation/``) ;
* ``systeme`` porte ``{id, code, libelle}`` ; chaque ligne porte EXACTEMENT
  ``{composant, role, unite, quantite, regle, produit_id, manquant}`` ;
* l'exemple montre au moins UNE ligne NON calculée : ``quantite`` à ``null``
  et ``manquant`` qui NOMME le paramètre absent — jamais une quantité de
  repli, jamais ``0`` ; une ligne calculée porte ``manquant: null`` ;
* les rôles sont ceux du vocabulaire contrôlé du catalogue ;
* ``exemple_vide`` (catalogue vide, l'état de toute société aujourd'hui) :
  aucun système, aucune ligne, un refus qui nomme ``systeme`` ;
* AUCUNE clé d'argent (D5).

Run :
    python manage.py test apps.calepinage.tests.test_calx335_contrat_fixation_bom -v2
"""
import json
import pathlib
import unittest

CHEMIN = (pathlib.Path(__file__).resolve().parents[1]
          / 'contract_samples' / 'calepinage_fixation_bom.json')
CONTRAT = json.loads(CHEMIN.read_text(encoding='utf-8'))

CLES_LIGNE = ['composant', 'manquant', 'produit_id', 'quantite', 'regle',
              'role', 'unite']
ROLES = {'rail', 'pince_milieu', 'pince_fin', 'crochet', 'embout', 'lest',
         'visserie'}
MOTS_D_ARGENT = ('prix', 'cout', 'coût', 'marge', 'montant', 'mad')


def _cles(objet):
    """Toutes les clés d'un objet JSON, à toute profondeur."""
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            yield cle
            yield from _cles(valeur)
    elif isinstance(objet, list):
        for valeur in objet:
            yield from _cles(valeur)


class ContratFixationBomTest(unittest.TestCase):

    def test_endpoint(self):
        self.assertEqual(
            CONTRAT['endpoint'],
            'GET /api/django/calepinage/calepinages/<int:pk>/bom-fixation/')
        self.assertTrue(CONTRAT['pourquoi'].strip())

    def test_trois_blocs_dans_chaque_etat(self):
        for etat in ('exemple', 'exemple_vide'):
            with self.subTest(etat=etat):
                self.assertEqual(sorted(CONTRAT[etat]),
                                 ['lignes', 'refus', 'systeme'])

    def test_systeme_applique(self):
        self.assertEqual(sorted(CONTRAT['exemple']['systeme']),
                         ['code', 'id', 'libelle'])
        self.assertEqual(CONTRAT['exemple']['refus'], [])

    def test_chaque_ligne_porte_les_sept_cles(self):
        for ligne in CONTRAT['exemple']['lignes']:
            with self.subTest(composant=ligne.get('composant')):
                self.assertEqual(sorted(ligne), CLES_LIGNE)
                self.assertIn(ligne['role'], ROLES)

    def test_une_ligne_non_calculee_nomme_son_manquant(self):
        non_calculees = [ligne for ligne in CONTRAT['exemple']['lignes']
                         if ligne['quantite'] is None]
        self.assertTrue(non_calculees,
                        "L'exemple doit montrer une ligne NON calculée.")
        for ligne in non_calculees:
            with self.subTest(composant=ligne['composant']):
                self.assertTrue(str(ligne['manquant'] or '').strip())

    def test_une_ligne_calculee_ne_porte_aucun_manquant(self):
        for ligne in CONTRAT['exemple']['lignes']:
            if ligne['quantite'] is not None:
                with self.subTest(composant=ligne['composant']):
                    self.assertIsNone(ligne['manquant'])
                    self.assertGreater(ligne['quantite'], 0)

    def test_aucune_quantite_de_repli_a_zero(self):
        for etat in ('exemple', 'exemple_vide'):
            for ligne in CONTRAT[etat]['lignes']:
                self.assertNotEqual(ligne['quantite'], 0)

    def test_quantite_unitaire_entiere(self):
        for ligne in CONTRAT['exemple']['lignes']:
            if ligne['unite'] == 'u' and ligne['quantite'] is not None:
                self.assertIsInstance(ligne['quantite'], int)

    def test_catalogue_vide_nomme_le_systeme(self):
        vide = CONTRAT['exemple_vide']
        self.assertIsNone(vide['systeme'])
        self.assertEqual(vide['lignes'], [])
        self.assertEqual([refus['champ'] for refus in vide['refus']],
                         ['systeme'])
        for refus in vide['refus']:
            self.assertEqual(sorted(refus), ['champ', 'message'])
            self.assertTrue(refus['message'].strip())

    def test_aucune_cle_d_argent(self):
        for etat in ('exemple', 'exemple_vide'):
            for cle in _cles(CONTRAT[etat]):
                with self.subTest(etat=etat, cle=cle):
                    self.assertFalse(
                        any(mot in cle.lower() for mot in MOTS_D_ARGENT),
                        f"clé d'argent « {cle} » dans une sortie technique")
