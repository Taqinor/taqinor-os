"""ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — le schéma d'étude refuse une
facture mensuelle « réelle » sous les lignes fixes du compteur (39,94 MAD
TTC/mois), comme la série ``estimerMois(1, 1600)`` de DEV-202609-0108.

Lancer :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_err_factures_plancher"
"""
from django.test import SimpleTestCase

from apps.ventes.domain.etude_schema import fusionner, valider

#: DEV-202609-0108 — exactement ``estimerMois(1, 1600)``.
SERIE_0108 = [1, 268, 534, 801, 1067, 1334, 1600, 1600, 1200, 801, 401, 1]


class FacturesPlancherTests(SimpleTestCase):

    def test_serie_sous_plancher_refusee(self):
        reproches = valider({'factures_mensuelles_reelles': SERIE_0108})
        self.assertEqual(len(reproches), 1, reproches)
        self.assertIn('lignes fixes', reproches[0])
        self.assertIn('39.94', reproches[0])
        self.assertIn('mois 1, 12', reproches[0])
        with self.assertRaises(ValueError):
            fusionner({}, factures_mensuelles_reelles=SERIE_0108)

    def test_zero_et_factures_plausibles_acceptes(self):
        self.assertEqual(valider({'factures_mensuelles_reelles':
                                  [0] + [900] * 11}), [])
        self.assertEqual(valider({'factures_mensuelles_reelles':
                                  [39.94] * 12}), [])
        self.assertEqual(valider({'factures_mensuelles_reelles': None}), [])

    def test_plancher_publie_au_schema_egal_a_la_garde(self):
        """ENF51 — la série publiée (PATCH ``etude-params``) refuse ce que la
        garde refuse : un élément conforme au schéma n'est jamais refusé."""
        import jsonschema

        from apps.ventes.views.openapi_docs import _proprietes_etude_params
        forme = dict(_proprietes_etude_params()['factures_mensuelles_reelles'])
        forme.pop('nullable')
        element = dict(forme['items'])
        # OpenAPI 3.0 (bornes exclusives booléennes) -> draft 4.
        for valeur in (0, -5, 0.0, 39.94, 40, 450.5, '', None, [], {}, True,
                       2.5443360298620274, 1, 39.93):
            conforme = jsonschema.Draft4Validator(element).is_valid(valeur)
            refuse = bool(valider({'factures_mensuelles_reelles': [valeur]}))
            self.assertEqual(conforme, not refuse, repr(valeur))
