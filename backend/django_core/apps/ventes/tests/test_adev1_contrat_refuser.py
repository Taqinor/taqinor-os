# -*- coding: utf-8 -*-
"""ADEV1 — le contrat du geste « Refuser » (PACT10) est posé SEUL sur main.

``contract_samples/devis_refuser.json`` déclare le corps exact
(``motif``/``note``/``date``/``marquer_lead_perdu``), la réponse 200, le 400
``{motif: [...]}`` et le 409 ``{detail, code}``. La vue et l'écran (ADEV44)
s'appuient sur CE fichier.

Test-du-test : retirer la clé ``motif`` du corps déclaré ⇒
``test_contrat_declare_corps_et_reponses`` échoue en la nommant.
"""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

CONTRAT = (Path(__file__).resolve().parents[1]
           / 'contract_samples' / 'devis_refuser.json')

CLES_CORPS = ('motif', 'note', 'date', 'marquer_lead_perdu')


class ContratRefuserTests(SimpleTestCase):

    def setUp(self):
        self.doc = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_contrat_declare_corps_et_reponses(self):
        doc = self.doc
        self.assertEqual(
            doc['endpoint'],
            'POST /api/django/ventes/devis/<int:pk>/refuser/')
        for cle in CLES_CORPS:
            self.assertIn(cle, doc['corps'],
                          f"clé de corps « {cle} » absente du contrat")
            self.assertIn(cle, doc['champs_corps'],
                          f"clé de corps « {cle} » non décrite")
        self.assertNotIn('motif_perte', doc['corps'],
                         "l'ancien corps `motif_perte: <id>` est abandonné")

        motif = doc['champs_corps']['motif']
        # AGRM37 ouverte : motif optionnel, mais la clause est gravée.
        self.assertIs(motif['obligatoire'], False)
        self.assertEqual(motif['obligatoire_si'], 'AGRM37 = oui')
        self.assertIn('motif_refus_valide', motif['valide_par'])
        self.assertEqual(doc['champs_corps']['note']['max_longueur'], 255)
        self.assertLessEqual(len(doc['corps']['note']), 255)
        self.assertRegex(doc['corps']['date'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertIsInstance(doc['corps']['marquer_lead_perdu'], bool)

        exemple = doc['exemple']
        self.assertEqual(exemple['statut'], 'refuse')
        self.assertEqual(exemple['motif_refus'], doc['corps']['motif'])
        self.assertTrue(
            re.match(r'^\d{4}-\d{2}-\d{2}$', exemple['date_refus']))

        rep = doc['reponses']
        self.assertEqual(
            rep['400'],
            {'motif': ['Choisissez un motif de refus de la liste.']})
        self.assertEqual(set(rep['409']), {'statut', 'version_remplacee'})
        for code, corps in rep['409'].items():
            self.assertEqual(set(corps), {'detail', 'code'})
            self.assertEqual(corps['code'], code)
            self.assertTrue(corps['detail'])

    def test_aucune_donnee_interne(self):
        brut = CONTRAT.read_text(encoding='utf-8')
        for interdit in ('prix_achat', 'marge'):
            self.assertNotIn(interdit, brut)
