"""QJR656 (contrat QJR506) — l'échantillon ``lead_provenance_fields.json``
est EXACTEMENT ``crm.selectors.LEAD_PROVENANCE_FIELDS``.

Le frontend (``fieldLabels.test.jsx``) lit cet échantillon et exige un
``libelleCourt`` pour chaque champ : sans ce lien, un champ ajouté côté serveur
s'afficherait sous son nom technique dans la bannière « valeurs du lead
modifiées ». Aucune base : pur contrat.

Run :
    python manage.py test apps.crm.tests_lead_provenance_fields_contract -v 2
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.crm import selectors

CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'lead_provenance_fields.json')


class EchantillonProvenanceEgalAuServeur(SimpleTestCase):
    def test_echantillon_egal_a_lead_provenance_fields(self):
        champs = json.loads(CONTRAT.read_text(encoding='utf-8'))[
            'exemple']['champs']
        self.assertEqual(len(champs), len(set(champs)), 'doublon')
        self.assertEqual(sorted(champs),
                         sorted(selectors.LEAD_PROVENANCE_FIELDS))
