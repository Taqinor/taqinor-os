# -*- coding: utf-8 -*-
"""ACAL292 — ``moteur/calculer`` sans les cinq tiroirs d'atelier AO.

Constat C-ACAL-141. Le pré-vol de ``calepiner`` chiffrait les cinq tiroirs AO
(dont une conception électrique « de référence », troisième modèle de
chaînage du produit) EN PLUS des suggestions : un document dont le coût par
variante ``c`` vérifie ``14c ≤ budget < 28c`` perdait ses suggestions (liste
vide) alors que l'écran (``PanneauAllees.jsx``) ne lit que ``suggestions``
et ``preuve`` — personne ne lisait ``tiroirs``. Les tiroirs sont retirés du
service, de la réponse et du contrat ``moteur_calculer.json``.

Le coût est celui du VRAI estimateur (``cout_estime``) : le budget du test
est posé à 14 fois le coût d'une variante, sans mock de la source.

Run :
    python manage.py test apps.calepinage.tests.test_acal_moteur_sans_tiroirs
"""
from __future__ import annotations

import inspect
import json
import pathlib

from django.test import SimpleTestCase

from core.calepinage.perf import BudgetCalcul

from apps.calepinage import moteur_io, moteur_service
from apps.calepinage.moteur_io import deriver_axe_rangee
from apps.calepinage.tests.test_axe_rangee_auto import _demande

CONTRAT = (pathlib.Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'moteur_calculer.json')


def _document():
    """Un champ 40 × 25 m, tables dos-à-dos, allée 0,60 m : le moteur y
    propose une « allée gratuite »."""
    document = deriver_axe_rangee(_demande(2, 180))
    document['parametres']['allee_min_m'] = 0.6
    document['parametres']['rives'] = {'laterale_m': 0.5,
                                       'extremite_m': 0.5}
    return document


class SansTiroirsTest(SimpleTestCase):

    def test_suggestions_servies_dans_la_fenetre_14c_28c(self):
        document = _document()
        c = moteur_service.cout_estime(document).millisecondes
        self.assertGreater(c, 0.0)
        multiplicateur = moteur_service.multiplicateur_suggestions()
        budget = BudgetCalcul(seuil_synchrone_ms=multiplicateur * c)
        resultat = moteur_service.calepiner(document, company=1,
                                            budget=budget)
        self.assertTrue(resultat['suggestions'],
                        'le budget tient 14c : les suggestions sont servies')
        self.assertIn('ALLEE_GRATUITE',
                      [s['code'] for s in resultat['suggestions']])
        self.assertIn('preuve', resultat)

    def test_reponse_sans_cle_tiroirs(self):
        resultat = moteur_service.calepinage_json(_document(), company=1)
        self.assertNotIn('tiroirs', resultat)
        self.assertNotIn('tiroirs', inspect.signature(
            moteur_service.calepinage_json).parameters)
        self.assertNotIn('tiroirs', inspect.signature(
            moteur_service.cout_estime).parameters)
        for nom in ('tiroirs_vers_json', 'tiroirs_vides',
                    'tiroir_electrique_vers_json', 'entree_electrique',
                    'module_de_reference', 'onduleur_de_reference',
                    'taille_chaine_du_preset', 'electrique_du_preset',
                    'patch_electrique_vers_params'):
            self.assertFalse(hasattr(moteur_io, nom), nom)
        for nom in ('multiplicateur_tiroirs', 'multiplicateur_electrique',
                    '_tiroirs_publiables', '_tiroir_electrique'):
            self.assertFalse(hasattr(moteur_service, nom), nom)

    def test_contrat_moteur_calculer_sans_tiroirs(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.assertNotIn('tiroirs', contrat['exemple'])
        self.assertIn('suggestions', contrat['exemple'])
        # La réponse réelle et le contrat portent les mêmes clés de charge
        # utile d'atelier.
        resultat = moteur_service.calepinage_json(_document(), company=1)
        self.assertEqual('tiroirs' in resultat, 'tiroirs' in contrat['exemple'])
