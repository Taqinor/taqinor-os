"""CALX25 — le contrat `contract_samples/calepinage_releve.json` est RÉEL.

Ce que ce fichier affirme, SANS base de données (`SimpleTestCase`) :

* la ``geometrie`` committée pour chaque chaîne du relevé est EXACTEMENT ce
  que ``services/releve.resoudre_chaines`` calcule pour la saisie ``chaines``
  committée à côté — jamais une valeur recopiée à la main puis figée. La
  cote « b » de « Pignon nord » (aucune valeur saisie, total mesuré 12,40 m)
  doit être DÉDUITE par fermeture et marquée ``A_CONFIRMER`` : c'est la
  garantie centrale de CAL64 (aucune cote inventée en silence) ;
* le libellé de l'azimut porte TOUJOURS sa précision déclarée (``±``), dans
  le format exact que ``services/releve._azimut`` produit ;
* l'enveloppe ``releve`` et l'entrée unique de ``releves`` portent les MÊMES
  clés — le POST rend le relevé qu'il vient de créer PLUS l'historique à
  jour, jamais deux vocabulaires.

Ce que ce fichier NE peut PAS affirmer sans base (documenté, pas caché) :
``enregistrer_releve`` (écrit un ``ReleveTerrain``) et ``releve_en_ligne``
(lit ``.photos`` sur une instance SAUVÉE) exigent un ``pk`` réel — ils
restent couverts par le test dédié à `ORM` (à écrire côté `TestCase`, hors de
portée de ce poste de développement sans Postgres/Docker) et par
``tests/test_cal223_contrats.py`` (déclaration + chemin).

Run :
    python manage.py test apps.calepinage.tests.test_calx25_releve_contrat -v 1
"""
from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.calepinage.services.releve import _azimut, resoudre_chaines

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'calepinage_releve.json').read_text(encoding='utf-8'))


class ContratReleveEstReelTest(SimpleTestCase):
    """Aucune base : `resoudre_chaines` et `_azimut` sont des fonctions pures."""

    def test_le_document_porte_les_trois_cles_attendues(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CONTRAT, f'clé « {cle} » absente du contrat.')
        self.assertEqual(CONTRAT['endpoint'],
                         'POST /api/django/calepinage/calepinages/'
                         '<int:pk>/releve/')

    def test_geometrie_committee_est_celle_que_le_solveur_calcule(self):
        releve = CONTRAT['exemple']['releve']
        obtenue = resoudre_chaines(releve['chaines'])
        self.assertEqual(
            obtenue, releve['geometrie'],
            "contract_samples/calepinage_releve.json a dérivé de "
            "services/releve.resoudre_chaines — régénérer l'exemple.")

    def test_cote_manquante_est_deduite_et_marquee_a_confirmer(self):
        # La garantie centrale de CAL64, affirmée sur l'exemple committé :
        # la cote « b » de « Pignon nord » n'a AUCUNE valeur saisie.
        pignon = next(c for c in CONTRAT['exemple']['releve']['chaines']
                      if c['nom'] == 'Pignon nord')
        self.assertIsNone(
            next(c['valeur'] for c in pignon['cotes'] if c['nom'] == 'b'))
        resolue = next(c for c in CONTRAT['exemple']['releve']['geometrie']['chaines']
                       if c['nom'] == 'Pignon nord')
        cote_b = next(c for c in resolue['cotes'] if c['nom'] == 'b')
        self.assertTrue(cote_b['a_confirmer'])
        self.assertEqual(cote_b['statut'], 'A_CONFIRMER')
        self.assertIn('Pignon nord / b',
                      CONTRAT['exemple']['releve']['geometrie']['cotes_a_confirmer'])

    def test_le_libelle_de_lazimut_porte_toujours_sa_precision(self):
        releve = CONTRAT['exemple']['releve']
        faux_releve = SimpleNamespace(
            azimut_boussole_deg=releve['azimut']['deg'],
            precision_azimut_deg=releve['azimut']['precision_deg'])
        self.assertEqual(_azimut(faux_releve), releve['azimut'])
        self.assertIn('±', releve['azimut']['libelle'])

    def test_lenveloppe_releve_et_lentree_de_releves_portent_les_memes_cles(self):
        exemple = CONTRAT['exemple']
        self.assertEqual(set(exemple['releve']), set(exemple['releves'][0]))
        self.assertEqual(exemple['releve'], exemple['releves'][0])
